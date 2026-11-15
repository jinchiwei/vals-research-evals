"""Run a submitted pipeline on one hidden case under a hard wall-clock limit.

Contract: the pipeline directory contains run.sh; we execute
    bash <pipeline>/run.sh INPUT_DIR OUTPUT_DIR
with stdin closed, a minimal environment, cwd = a fresh per-case home directory and
a new session (so it is its own process group).

Guarantees (and their limits):
- Time is measured by this process with time.monotonic() from just before the spawn until
  the main process is reaped. Nothing the pipeline writes (logs, timing files) is ever read
  here, so self-reported timing cannot influence the result.
- On reaching the limit the whole process group is sent SIGKILL at once (a hard limit,
  no grace period). After any exit the group is killed again, so background children left
  in the group do not survive into grading.
- When this process is root, the pipeline runs as an unprivileged uid/gid (default 65534,
  nobody/nogroup) with no supplementary groups, and after the run every process of that uid
  is killed (this also catches children that escaped the group with setsid). When not root
  (local tests), the pipeline runs as the current user and only the group kill applies.
- stdout and stderr are merged and captured by the parent through a pipe; at most
  log_cap_bytes are kept (head and tail halves), so a chatty pipeline cannot fill the disk.
- No network is assumed or provided here; network isolation is the sandbox's job
  ([verifier] network_mode = "no-network").
- Optional address-space limit (RLIMIT_AS) because Modal does not hard-cap RAM. Core dumps
  are disabled.
"""
import collections
import os
import resource
import signal
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

UNPRIVILEGED_UID = 65534
DEFAULT_LOG_CAP = 256 * 1024
DEFAULT_PATH = '/opt/benchmark-venv/bin:/usr/local/bin:/usr/bin:/bin'


@dataclass
class RunResult:
    wall_seconds: float          # measured by the grader, never by the pipeline
    time_limit_seconds: float
    timed_out: bool
    exit_code: int | None        # None when killed on timeout; negative = killed by that signal
    log_bytes_total: int
    log_truncated: bool
    ran_as_uid: int
    log_path: str | None

    def to_dict(self):
        return asdict(self)


class _CappedReader(threading.Thread):
    """Drain a pipe; keep the first and last cap/2 bytes; count everything."""

    def __init__(self, stream, cap):
        super().__init__(daemon=True)
        self.stream, self.cap = stream, cap
        self.head = bytearray()
        self.tail = collections.deque()
        self.tail_bytes = 0
        self.total = 0

    def run(self):
        half = self.cap // 2
        try:
            while True:
                chunk = self.stream.read1(65536) if hasattr(self.stream, 'read1') else self.stream.read(65536)
                if not chunk:
                    break
                self.total += len(chunk)
                room = half - len(self.head)
                if room > 0:
                    self.head += chunk[:room]
                    chunk = chunk[room:]
                if chunk:
                    self.tail.append(chunk)
                    self.tail_bytes += len(chunk)
                    while self.tail and self.tail_bytes - len(self.tail[0]) >= half:
                        self.tail_bytes -= len(self.tail.popleft())
        except (OSError, ValueError):
            pass

    def text(self):
        tail = b''.join(self.tail)[-(self.cap // 2):] if self.tail else b''
        kept = len(self.head) + len(tail)
        middle = b''
        if self.total > kept:
            middle = f'\n[... {self.total - kept} bytes omitted by the grader ...]\n'.encode()
        return bytes(self.head) + middle + tail, self.total > kept


def _kill_group(pgid):
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def kill_uid(uid):
    """SIGKILL every process whose real uid is `uid` (scan of /proc; root only). Returns count."""
    if os.geteuid() != 0 or uid == 0:
        return 0
    killed = 0
    for _ in range(3):                      # repeat: a dying parent may have just forked
        found = 0
        for entry in os.listdir('/proc'):
            if not entry.isdigit():
                continue
            try:
                with open(f'/proc/{entry}/status') as handle:
                    for line in handle:
                        if line.startswith('Uid:'):
                            if int(line.split()[1]) == uid:
                                os.kill(int(entry), signal.SIGKILL)
                                found += 1
                            break
            except (OSError, ValueError):
                continue
        killed += found
        if not found:
            break
        time.sleep(0.05)
    return killed


def _limits(memory_bytes):
    def apply():
        # PR_SET_NO_NEW_PRIVS (38): setuid binaries in the image cannot regain privilege.
        try:
            import ctypes
            ctypes.CDLL(None, use_errno=True).prctl(38, 1, 0, 0, 0)
        except OSError:
            pass
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        if memory_bytes:
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    return apply


def pipeline_env(home, path=DEFAULT_PATH, threads=None, extra=None):
    """Minimal environment for the pipeline. Nothing from the grader's environment leaks in."""
    env = {'PATH': path, 'HOME': str(home), 'TMPDIR': str(Path(home) / 'tmp'), 'LANG': 'C.UTF-8',
           'LC_ALL': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1', 'PIP_NO_INDEX': '1',
           'MPLCONFIGDIR': str(Path(home) / 'tmp'), 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'}
    if threads:
        for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                     'ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS', 'NUMEXPR_NUM_THREADS'):
            env[name] = str(int(threads))
    env.update(extra or {})
    return env


def run_pipeline(pipeline_dir, input_dir, output_dir, time_limit_seconds, *, home_dir, log_path=None,
                 log_cap_bytes=DEFAULT_LOG_CAP, path=DEFAULT_PATH, threads=None, memory_bytes=None,
                 uid=UNPRIVILEGED_UID, extra_env=None):
    """Run `bash pipeline_dir/run.sh input_dir output_dir` once. See the module docstring.

    The caller prepares input_dir (readable), output_dir and home_dir (writable by the run
    user). Returns RunResult; never raises for pipeline misbehaviour (missing run.sh is
    reported as exit code 127 by bash).
    """
    if time_limit_seconds <= 0:
        raise ValueError('time limit must be positive')
    home = Path(home_dir)
    (home / 'tmp').mkdir(parents=True, exist_ok=True)
    as_root = os.geteuid() == 0
    run_uid = uid if as_root else os.geteuid()
    if as_root:
        for d in (home, home / 'tmp'):
            os.chown(d, uid, uid)
    cmd = ['/bin/bash', str(Path(pipeline_dir) / 'run.sh'), str(input_dir), str(output_dir)]
    kwargs = dict(stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                  cwd=str(home), env=pipeline_env(home, path, threads, extra_env), close_fds=True,
                  start_new_session=True, preexec_fn=_limits(memory_bytes))
    if as_root:
        kwargs.update(user=uid, group=uid, extra_groups=[])
    timed_out = False
    start = time.monotonic()
    process = subprocess.Popen(cmd, **kwargs)
    reader = _CappedReader(process.stdout, log_cap_bytes)
    reader.start()
    try:
        process.wait(timeout=time_limit_seconds)
        wall = time.monotonic() - start
    except subprocess.TimeoutExpired:
        wall = time.monotonic() - start
        timed_out = True
        _kill_group(process.pid)
        process.wait()
    finally:
        _kill_group(process.pid)            # leftover background children in the group
        if as_root:
            kill_uid(uid)                   # children that escaped the group
    reader.join(timeout=2.0)                # an escaped child (non-root case) may hold the pipe
    try:
        process.stdout.close()
    except Exception:                       # the reader may still be blocked on an escaped child
        pass
    data, truncated = reader.text()
    if log_path is not None:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        Path(log_path).write_bytes(data)
    return RunResult(wall_seconds=wall, time_limit_seconds=float(time_limit_seconds), timed_out=timed_out,
                     exit_code=None if timed_out else process.returncode, log_bytes_total=reader.total,
                     log_truncated=truncated, ran_as_uid=run_uid,
                     log_path=None if log_path is None else str(log_path))
