"""Tests for agents/pcnsl_claude (the single-attempt Claude Code wrapper).

The Claude CLI is replaced by a fake executable only at the process boundary: the real
wrapper builds argv, spawns the process, enforces the timeout and writes run.json.
The fake reads its behaviour from a file beside itself, because the wrapper passes the
child an allowlisted environment.
"""

import importlib.util
import json
import os
import shlex
import stat
import sys
import tempfile
import unittest
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[1] / "agents" / "pcnsl_claude"
_spec = importlib.util.spec_from_file_location("pcnsl_claude_run_agent", AGENT_DIR / "run_agent.py")
ra = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ra)

try:
    from valkyrie.sdk.models.agents import AgentContract
except ImportError:  # SDK lives in .venv-valkyrie
    AgentContract = None

FAKE_CLAUDE = """#!{python}
import json, os, sys, time
from pathlib import Path
here = Path(__file__).resolve().parent
cfg = json.loads((here / "fake_config.json").read_text())
if sys.argv[1:] == ["--version"]:
    print(cfg.get("version", "{version}") + " (Claude Code)")
    sys.exit(0)
stdin = sys.stdin.read()
with open(here / "calls.jsonl", "a") as fh:
    fh.write(json.dumps({{
        "argv": sys.argv[1:], "stdin": stdin, "cwd": os.getcwd(),
        "env_keys": sorted(os.environ),
        "key_matches": os.environ.get("ANTHROPIC_API_KEY") == cfg.get("expected_key"),
        "home": os.environ.get("HOME"),
    }}) + "\\n")
print(json.dumps({{"type": "system", "subtype": "init"}}), flush=True)
time.sleep(cfg.get("sleep", 0))
print(json.dumps({{"type": "result", "subtype": cfg.get("subtype", "success"),
                  "is_error": cfg.get("exit", 0) != 0, "num_turns": 7,
                  "total_cost_usd": 0.42, "usage": {{"input_tokens": 10, "output_tokens": 5}},
                  "result": "MODEL TEXT", "session_id": "s-1"}}), flush=True)
sys.stderr.write("fake stderr\\n")
sys.exit(cfg.get("exit", 0))
"""

KEY = "sk-test-NOT-A-REAL-KEY-123"


class FakeRuntime:
    def __init__(self, root: Path, **cfg):
        self.root = root
        self.agent_env = root / "agent-env"
        self.bin = self.agent_env / "bin"
        self.bin.mkdir(parents=True)
        self.exe = self.bin / "claude"
        self.exe.write_text(FAKE_CLAUDE.format(python=sys.executable, version=ra.PINNED_CLI_VERSION))
        self.exe.chmod(self.exe.stat().st_mode | stat.S_IXUSR)
        self.configure(**cfg)
        self.venv = root / "venv"
        self.venv.mkdir()
        self.logs = root / "logs" / "pcnsl-claude"
        self.workdir = root / "workspace"
        self.workdir.mkdir()

    def configure(self, **cfg):
        cfg.setdefault("expected_key", KEY)
        (self.bin / "fake_config.json").write_text(json.dumps(cfg))

    def calls(self):
        path = self.bin / "calls.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines()]

    def problem(self, text="Predict the held-out probabilities.\n"):
        path = self.root / "instruction.md"
        path.write_text(text)
        return path


class AgentTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._env = dict(os.environ)
        self.err_path = self.root / "valkyrie_error.txt"
        os.environ["VALKYRIE_ERROR_PATH"] = str(self.err_path)
        os.environ[ra.API_KEY_ENV] = KEY
        self._cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self._cwd)
        os.environ.clear()
        os.environ.update(self._env)
        self._tmp.cleanup()

    def run_wrapper(self, rt, *extra, problem=None, model="anthropic/claude-opus-5-5"):
        os.chdir(rt.workdir)
        argv = ["run", str(problem or rt.problem()), "--task-id", "myd88-fold0", "--model", model,
                "--agent-env", str(rt.agent_env), "--benchmark-venv", str(rt.venv),
                "--log-dir", str(rt.logs), *extra]
        return ra.main(argv)

    def meta(self, rt):
        return json.loads((rt.logs / "run.json").read_text())


class RuntimeCheckTests(AgentTestCase):
    def check(self, rt, global_dirs=(), **kw):
        return ra.check_runtime(rt.agent_env, rt.venv, global_dirs=global_dirs,
                                python_prefix=str(rt.venv), **kw)

    def test_prepared_runtime_passes(self):
        rt = FakeRuntime(self.root)
        info = self.check(rt)
        self.assertEqual(info["version"], ra.PINNED_CLI_VERSION)
        self.assertEqual(rt.calls(), [])  # --version only; no task run

    def test_missing_executable_rejected(self):
        rt = FakeRuntime(self.root)
        rt.exe.unlink()
        with self.assertRaisesRegex(ra.RuntimeCheckError, "missing"):
            self.check(rt)

    def test_executable_resolving_outside_agent_env_rejected(self):
        rt = FakeRuntime(self.root)
        outside = self.root / "usr-local-bin"
        outside.mkdir()
        os.replace(rt.exe, outside / "claude")
        rt.exe.symlink_to(outside / "claude")
        with self.assertRaisesRegex(ra.RuntimeCheckError, "global installs are not allowed"):
            self.check(rt)

    def test_global_install_alongside_rejected(self):
        rt = FakeRuntime(self.root)
        global_dir = self.root / "dot-local-bin"
        global_dir.mkdir()
        (global_dir / "claude").symlink_to(self.root / "dangling")
        with self.assertRaisesRegex(ra.RuntimeCheckError, "global Claude install"):
            self.check(rt, global_dirs=(str(global_dir),))

    def test_version_mismatch_rejected(self):
        rt = FakeRuntime(self.root, version="9.9.9")
        with self.assertRaisesRegex(ra.RuntimeCheckError, "9.9.9"):
            self.check(rt)

    def test_system_python_rejected(self):
        rt = FakeRuntime(self.root)
        with self.assertRaisesRegex(ra.RuntimeCheckError, "Python prefix"):
            ra.check_runtime(rt.agent_env, rt.venv, global_dirs=(), python_prefix="/usr")

    def test_check_subcommand_exit_code(self):
        rt = FakeRuntime(self.root)
        rt.exe.unlink()
        self.assertEqual(ra.main(["check", "--agent-env", str(rt.agent_env),
                                  "--benchmark-venv", str(rt.venv)]), 1)


class WrapperTests(AgentTestCase):
    def test_forwards_model_effort_budget_and_prompt_without_shell(self):
        rt = FakeRuntime(self.root)
        prompt = "Write /workspace/output/predictions.csv; $(touch PWNED) `id` && rm -rf x\n"
        code = self.run_wrapper(rt, "--effort", "high", "--max-budget-usd", "5.0",
                                problem=rt.problem(prompt))
        self.assertEqual(code, 0)
        [call] = rt.calls()
        argv = call["argv"]

        def flag(name):
            return argv[argv.index(name) + 1]

        self.assertEqual(flag("--model"), "claude-opus-5-5")
        self.assertEqual(flag("--effort"), "high")
        self.assertEqual(flag("--max-budget-usd"), "5")
        self.assertEqual(flag("--output-format"), "stream-json")
        self.assertIn("--print", argv)
        self.assertNotIn("--max-turns", argv)  # not offered by the pinned CLI
        self.assertEqual(call["stdin"], prompt)  # prompt via stdin, verbatim
        self.assertFalse(any(prompt.strip() in a for a in argv))
        self.assertFalse((rt.workdir / "PWNED").exists())
        self.assertEqual(Path(call["cwd"]).resolve(), rt.workdir.resolve())
        self.assertTrue(call["key_matches"])
        home = Path(call["home"]).resolve()
        self.assertFalse(home.is_relative_to(rt.logs.resolve()))  # not carried in final_output
        self.assertEqual(sorted(p.name for p in rt.logs.iterdir()),
                         ["attempt.lock", "run.json", "stderr.log", "stream.jsonl"])
        self.assertNotIn("VALKYRIE_ERROR_PATH", call["env_keys"])

        meta = self.meta(rt)
        self.assertEqual(meta["exit_code"], 0)
        self.assertEqual(meta["status"], "exited")
        self.assertEqual(meta["attempt"], 1)
        self.assertEqual(meta["result"]["num_turns"], 7)
        self.assertEqual(meta["result"]["total_cost_usd"], 0.42)
        self.assertNotIn("result", meta["result"])  # model text stays in stream.jsonl only
        self.assertTrue((rt.logs / "stream.jsonl").read_text().count('"type": "result"') == 1)
        self.assertFalse(self.err_path.exists())

    def test_api_key_never_in_argv_or_files(self):
        rt = FakeRuntime(self.root)
        self.run_wrapper(rt)
        self.assertNotIn(KEY, json.dumps(rt.calls()[0]["argv"]))
        for path in rt.logs.rglob("*"):
            if path.is_file():
                self.assertNotIn(KEY, path.read_text(errors="replace"), path)

    def test_nonzero_exit_recorded_and_returned(self):
        rt = FakeRuntime(self.root, exit=7, subtype="error_max_budget_usd")
        code = self.run_wrapper(rt)
        self.assertEqual(code, 7)
        meta = self.meta(rt)
        self.assertEqual((meta["status"], meta["exit_code"]), ("failed", 7))
        self.assertTrue(meta["result"]["is_error"])
        self.assertEqual(meta["result"]["subtype"], "error_max_budget_usd")
        self.assertEqual(self.err_path.read_text().strip(), "AgentError: Claude Code exited with code 7")
        self.assertEqual(len(rt.calls()), 1)  # no automatic retry

    def test_second_attempt_in_same_sandbox_refused(self):
        rt = FakeRuntime(self.root, exit=1)
        self.assertEqual(self.run_wrapper(rt), 1)
        self.assertEqual(self.run_wrapper(rt), 3)
        self.assertEqual(len(rt.calls()), 1)
        self.assertEqual(self.meta(rt)["exit_code"], 1)  # first attempt's record kept

    def test_timeout_stops_process_and_is_recorded(self):
        rt = FakeRuntime(self.root, sleep=30)
        code = self.run_wrapper(rt, "--timeout-sec", "1")
        self.assertEqual(code, ra.TIMEOUT_EXIT)
        meta = self.meta(rt)
        self.assertTrue(meta["timed_out"])
        self.assertEqual(meta["status"], "timeout")
        self.assertIsNone(meta["result"])  # no fabricated result event
        self.assertLess(meta["elapsed_sec"], 15)

    def test_missing_api_key_refused_before_spawn(self):
        rt = FakeRuntime(self.root)
        del os.environ[ra.API_KEY_ENV]
        self.assertEqual(self.run_wrapper(rt), 2)
        self.assertEqual(rt.calls(), [])
        self.assertEqual(self.meta(rt)["status"], "rejected")

    def test_budget_above_cap_and_overlong_timeout_refused(self):
        for extra in (("--max-budget-usd", "5.01"), ("--timeout-sec", "1801")):
            with self.subTest(extra=extra):
                rt = FakeRuntime(self.root / extra[0].strip("-"))
                self.assertEqual(self.run_wrapper(rt, *extra), 2)
                self.assertEqual(rt.calls(), [])

    def test_non_anthropic_model_refused(self):
        for model in ("openai/gpt-5", "anthropic/claude-x; rm -rf /", "sonnet"):
            with self.subTest(model=model):
                rt = FakeRuntime(self.root / str(abs(hash(model))))
                self.assertEqual(self.run_wrapper(rt, model=model), 2)
                self.assertEqual(rt.calls(), [])


@unittest.skipIf(AgentContract is None, "valkyrie SDK not importable (use .venv-valkyrie/bin/python)")
class ContractTests(AgentTestCase):
    def test_contract_validates_and_rendered_command_drives_wrapper(self):
        contract = AgentContract.from_directory(AGENT_DIR)
        self.assertEqual(contract.name, AGENT_DIR.name)
        self.assertEqual(contract.install_egress, [])
        self.assertFalse(contract.allow_provider_tools)
        self.assertEqual(contract.secrets, {"ANTHROPIC_API_KEY": "anthropic-api-key"})
        self.assertIn("check", contract.install_cmd.split())

        kwargs = contract.validate_kwargs({}, model="anthropic/claude-opus-5-5")
        self.assertEqual(kwargs["effort"], "high")
        self.assertEqual(kwargs["max_budget_usd"], 5.0)
        self.assertEqual(kwargs["timeout_sec"], 1740)
        with self.assertRaises(Exception):
            contract.validate_kwargs({"effort": "ultra"}, model="anthropic/claude-opus-5-5")

        rt = FakeRuntime(self.root)
        # Tracker stringifies validated kwargs and fills placeholders before `sh -c`.
        bindings = {k: str(v) for k, v in kwargs.items()}
        bindings.update(problem_statement_path=str(rt.problem()), task_id="myd88-fold0")
        cmd = contract.run_cmd
        for name, value in bindings.items():
            cmd = cmd.replace("{" + name + "}", value)
        self.assertNotIn("{", cmd)
        words = shlex.split(cmd)
        self.assertEqual(words[:3], ["/opt/benchmark-venv/bin/python", "-I",
                                     f"/bundle/{contract.name}/run_agent.py"])
        os.chdir(rt.workdir)
        code = ra.main(words[3:] + ["--agent-env", str(rt.agent_env), "--benchmark-venv", str(rt.venv),
                                    "--log-dir", str(rt.logs)])
        self.assertEqual(code, 0)
        argv = rt.calls()[0]["argv"]
        self.assertEqual(argv[argv.index("--effort") + 1], "high")
        self.assertEqual(argv[argv.index("--max-budget-usd") + 1], "5")
        self.assertEqual(self.meta(rt)["timeout_sec"], 1740)


if __name__ == "__main__":
    unittest.main()
