"""Runner: hard wall-clock limit, process-group kill, ignored self-reported timing, capped logs,
minimal environment. Runs as the current (non-root) user; the uid drop needs a root verifier."""
import os
import sys
import time
from pathlib import Path

import pytest

from suite.core import runner

PATH = f'{Path(sys.executable).parent}:/usr/bin:/bin'


def pipeline(tmp_path, body):
    d = tmp_path / 'pipeline'
    d.mkdir()
    (d / 'run.sh').write_text('#!/bin/bash\nset -u\nIN="$1"; OUT="$2"\n' + body + '\n')
    for name in ('in', 'out'):
        (tmp_path / name).mkdir()
    return d


def run(tmp_path, d, limit, **kw):
    return runner.run_pipeline(d, tmp_path / 'in', tmp_path / 'out', limit, home_dir=tmp_path / 'home',
                               log_path=tmp_path / 'log.txt', path=PATH, **kw)


def _alive(pid):
    try:
        with open(f'/proc/{pid}/status') as f:
            return 'zombie' not in f.read()
    except FileNotFoundError:
        return False


def test_normal_run(tmp_path):
    d = pipeline(tmp_path, 'echo hello; echo result > "$OUT/x.txt"')
    r = run(tmp_path, d, 10)
    assert r.exit_code == 0 and not r.timed_out and 0 < r.wall_seconds < 10
    assert (tmp_path / 'out' / 'x.txt').read_text() == 'result\n'
    assert (tmp_path / 'log.txt').read_text() == 'hello\n'
    assert r.ran_as_uid == os.geteuid()


def test_time_limit_enforced_and_self_reported_timing_ignored(tmp_path):
    d = pipeline(tmp_path, 'echo \'{"wall_seconds": 0.001}\' > "$OUT/timing.json"\n'
                           'echo "elapsed 0.001 s"\nsleep 30')
    start = time.monotonic()
    r = run(tmp_path, d, 1.0)
    assert r.timed_out and r.exit_code is None
    assert 1.0 <= r.wall_seconds < 3.0                 # grader clock, not the 0.001 s the pipeline claims
    assert time.monotonic() - start < 6.0              # the sleep was killed, not waited for


def test_process_group_killed_after_exit_and_on_timeout(tmp_path):
    d = pipeline(tmp_path, 'sleep 60 &\necho $! > "$OUT/bg.pid"\nexit 0')
    r = run(tmp_path, d, 10)
    assert r.exit_code == 0
    pid = int((tmp_path / 'out' / 'bg.pid').read_text())
    time.sleep(0.2)
    assert not _alive(pid)
    d2 = tmp_path / 't2'
    d2.mkdir()
    p2 = pipeline(d2, 'sleep 60 &\necho $! > "$OUT/bg.pid"\nsleep 60')
    r2 = run(d2, p2, 1.0)
    assert r2.timed_out
    time.sleep(0.2)
    assert not _alive(int((d2 / 'out' / 'bg.pid').read_text()))


def test_log_is_capped(tmp_path):
    d = pipeline(tmp_path, 'head -c 1000000 /dev/zero | tr "\\0" a; echo; echo THE-END')
    r = run(tmp_path, d, 20, log_cap_bytes=10_000)
    log = (tmp_path / 'log.txt').read_bytes()
    assert r.log_truncated and r.log_bytes_total > 1_000_000
    assert len(log) < 10_200 and b'omitted by the grader' in log and log.endswith(b'THE-END\n')


def test_environment_is_minimal(tmp_path, monkeypatch):
    monkeypatch.setenv('SUITE_TEST_SECRET', 'leak')
    d = pipeline(tmp_path, 'echo "secret=${SUITE_TEST_SECRET:-}" > "$OUT/env.txt"; echo "home=$HOME" >> "$OUT/env.txt"'
                           '; echo "threads=$OMP_NUM_THREADS" >> "$OUT/env.txt"')
    run(tmp_path, d, 10, threads=3)
    text = (tmp_path / 'out' / 'env.txt').read_text()
    assert 'secret=\n' in text and f'home={tmp_path / "home"}' in text and 'threads=3' in text


def test_missing_entry_point_and_failure_codes(tmp_path):
    d = tmp_path / 'empty'
    d.mkdir()
    (tmp_path / 'in').mkdir()
    (tmp_path / 'out').mkdir()
    assert run(tmp_path, d, 5).exit_code == 127
    d2 = tmp_path / 'b'
    d2.mkdir()
    p = pipeline(d2, 'exit 3')
    assert run(d2, p, 5).exit_code == 3
    with pytest.raises(ValueError):
        run(d2, p, 0)
