"""Small client for UCSF Versa (the university's model gateway).

Two routes, chosen from the model ID:

  anthropic  Claude models through the Bedrock-style gateway (AnthropicBedrock SDK).
             Credentials: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
             Optional:    AWS_REGION (us-west-2), ANTHROPIC_BEDROCK_BASE_URL
  openai     OpenAI models through the Azure-style gateway (AzureOpenAI SDK).
             Credentials: VERSA_API_KEY
             Optional:    VERSA_ENDPOINT, VERSA_API_VERSION

Credentials come from the environment only. `load_env_file()` can copy them in from a
KEY=VALUE file (for example ~/versa_key.env) without ever printing them. Nothing in this
module prints, logs or returns a credential; error text is scrubbed before it is returned.

Every call has a timeout, a cap on output tokens, a cap on returned characters, and comes
back as a `VersaResult` (never an exception) carrying the text, token usage and latency.

Versa is reachable from the UCSF network only (campus or VPN). It is not reachable from a
sandbox without network access.

CLI:
  python versa_client.py models                 # IDs this file knows, with verification status
  python versa_client.py catalog                # live deployment list from the OpenAI route
  python versa_client.py health --model ID      # one synthetic call ("Reply with exactly: OK")
  python versa_client.py call --model ID --prompt-file p.txt [--system-file s.txt] [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_BEDROCK_BASE_URL = "https://unified-api.ucsf.edu/general/awsai"
DEFAULT_AWS_REGION = "us-west-2"
DEFAULT_OPENAI_ENDPOINT = "https://unified-api.ucsf.edu/general"
DEFAULT_OPENAI_API_VERSION = "2025-04-01-preview"

DEFAULT_TIMEOUT_S = 180.0
DEFAULT_MAX_OUTPUT_TOKENS = 4096
HARD_MAX_OUTPUT_TOKENS = 32000
DEFAULT_MAX_CHARS = 20000
MAX_PROMPT_CHARS = 400_000

# Model IDs from the lab's shared list (/data/rauschecker2/jkw/aria/dev/src/utils/versa_models.py)
# as of 2026-11-14. "verified" is filled in by REPORT.md from live calls, not assumed here.
ANTHROPIC_MODELS = (
    "us.anthropic.claude-opus-5-5",
    "us.anthropic.claude-sonnet-5-5",
    "us.anthropic.claude-haiku-5-5",
    "us.anthropic.claude-opus-4-8",
    "us.anthropic.claude-opus-4-6-v1",
    "us.anthropic.claude-sonnet-4-6",
    "us.anthropic.claude-opus-4-5-20251101-v1:0",
    "us.anthropic.claude-opus-4-1-20250805-v1:0",
    "us.anthropic.claude-sonnet-4-20250514-v1:0",
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "anthropic.claude-3-5-sonnet-20240620-v1:0",
)
OPENAI_MODELS = (
    "gpt-5.2-2025-12-11",
    "gpt-5-2025-08-07",
    "gpt-5-mini-2025-08-07",
    "gpt-5-nano-2025-08-07",
    "gpt-4.1-2025-04-14",
    "o4-mini-2025-04-16",
    "o3-mini-2025-01-31",
    "o1-2024-12-17",
    "o1-mini-2024-09-12",
    "gpt-4o-2024-08-06",
    "gpt-4o-mini-2024-07-18",
    "gpt-4-turbo-2024-04-09",
    "gpt-4-turbo-128k",
    "gpt-35-turbo",
)

_SECRET_ENV_NAMES = (
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
    "VERSA_AWS_ACCESS_KEY_ID", "VERSA_AWS_SECRET_ACCESS_KEY",
    "VERSA_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "TABPFN_TOKEN", "HF_TOKEN",
)
_ENV_FILE_ALLOWED = {
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_REGION",
    "ANTHROPIC_BEDROCK_BASE_URL", "VERSA_API_KEY", "VERSA_ENDPOINT", "VERSA_API_VERSION",
    "VERSA_AWS_ACCESS_KEY_ID", "VERSA_AWS_SECRET_ACCESS_KEY",
}
_ENV_FILE_ALIASES = {
    "VERSA_AWS_ACCESS_KEY_ID": "AWS_ACCESS_KEY_ID",
    "VERSA_AWS_SECRET_ACCESS_KEY": "AWS_SECRET_ACCESS_KEY",
}


@dataclass
class VersaResult:
    ok: bool
    route: str
    model_requested: str
    model_reported: str | None = None
    text: str = ""
    truncated: bool = False
    stop_reason: str | None = None
    usage: dict[str, int] = field(default_factory=dict)
    latency_s: float = 0.0
    request_id: str | None = None
    error_type: str | None = None
    status_code: int | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class VersaConfigError(RuntimeError):
    """Missing or unusable configuration. The message never contains a credential value."""


def load_env_file(path: str | os.PathLike[str], override: bool = False) -> list[str]:
    """Copy Versa settings from a KEY=VALUE file into os.environ.

    Only names this client uses are read; everything else in the file is ignored. Returns the
    NAMES that were set, never the values. `VERSA_AWS_*` names are also mapped to `AWS_*`.
    """
    set_names: list[str] = []
    for raw in Path(path).expanduser().read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip().strip("'\"")
        if name not in _ENV_FILE_ALLOWED or not value:
            continue
        for target in {name, _ENV_FILE_ALIASES.get(name, name)}:
            if override or not os.environ.get(target):
                os.environ[target] = value
                set_names.append(target)
    return sorted(set(set_names))


def route_for(model: str) -> str:
    """'anthropic' or 'openai' for a model ID; raises VersaConfigError when it is neither."""
    m = model.lower()
    if model in ANTHROPIC_MODELS or "anthropic" in m or "claude" in m:
        return "anthropic"
    if model in OPENAI_MODELS or m.startswith(("gpt-", "o1", "o3", "o4")):
        return "openai"
    raise VersaConfigError(f"cannot tell which Versa route serves model {model!r}")


def sanitize(text: Any, limit: int = 400) -> str:
    """Error text that is safe to print: credential values and key-like strings removed."""
    s = str(text)
    for name in _SECRET_ENV_NAMES:
        value = os.environ.get(name)
        if value and len(value) >= 6:
            s = s.replace(value, f"<{name}>")
    s = re.sub(r"(?i)\b(bearer|basic)\s+\S+", r"\1 <redacted>", s)
    s = re.sub(r"(?i)(api[-_ ]?key|authorization|x-amz-security-token|signature|credential)"
               r"(\s*[=:]\s*)(?!(?:bearer|basic) <redacted>)\S+", r"\1\2<redacted>", s)
    s = re.sub(r"\b(AKIA|ASIA)[A-Z0-9]{12,}\b", "<aws-key-id>", s)
    s = re.sub(r"[A-Za-z0-9+/_\-]{32,}={0,2}", "<redacted>", s)
    s = " ".join(s.split())
    return s if len(s) <= limit else s[:limit] + "…"


def _bound_tokens(n: int | None) -> int:
    n = DEFAULT_MAX_OUTPUT_TOKENS if n is None else int(n)
    if n < 1:
        raise VersaConfigError("max_output_tokens must be at least 1")
    return min(n, HARD_MAX_OUTPUT_TOKENS)


def _bound_text(text: str, max_chars: int) -> tuple[str, bool]:
    return (text, False) if len(text) <= max_chars else (text[:max_chars], True)


def _error_result(route: str, model: str, exc: BaseException, started: float) -> VersaResult:
    status = getattr(exc, "status_code", None)
    return VersaResult(
        ok=False, route=route, model_requested=model, latency_s=round(time.monotonic() - started, 3),
        error_type=type(exc).__name__, status_code=status if isinstance(status, int) else None,
        error=sanitize(getattr(exc, "message", None) or exc),
        request_id=getattr(exc, "request_id", None),
    )


class VersaClient:
    """Calls Versa. Build once and reuse; SDK clients are created on first use per route."""

    def __init__(self, timeout_s: float = DEFAULT_TIMEOUT_S, max_retries: int = 2,
                 max_chars: int = DEFAULT_MAX_CHARS,
                 anthropic_client: Any = None, openai_client: Any = None) -> None:
        self.timeout_s = float(timeout_s)
        self.max_retries = int(max_retries)
        self.max_chars = int(max_chars)
        self._anthropic = anthropic_client
        self._openai = openai_client

    # -- client construction -------------------------------------------------------------
    def _anthropic_client(self) -> Any:
        if self._anthropic is None:
            key, secret = os.environ.get("AWS_ACCESS_KEY_ID"), os.environ.get("AWS_SECRET_ACCESS_KEY")
            if not key or not secret:
                raise VersaConfigError(
                    "anthropic route needs AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in the environment")
            from anthropic import AnthropicBedrock
            kwargs: dict[str, Any] = dict(
                aws_access_key=key, aws_secret_key=secret,
                aws_region=os.environ.get("AWS_REGION") or DEFAULT_AWS_REGION,
                base_url=os.environ.get("ANTHROPIC_BEDROCK_BASE_URL") or DEFAULT_BEDROCK_BASE_URL,
                timeout=self.timeout_s, max_retries=self.max_retries,
            )
            if os.environ.get("AWS_SESSION_TOKEN"):
                kwargs["aws_session_token"] = os.environ["AWS_SESSION_TOKEN"]
            self._anthropic = AnthropicBedrock(**kwargs)
        return self._anthropic

    def _openai_client(self) -> Any:
        if self._openai is None:
            key = os.environ.get("VERSA_API_KEY")
            if not key:
                raise VersaConfigError("openai route needs VERSA_API_KEY in the environment")
            from openai import AzureOpenAI
            self._openai = AzureOpenAI(
                api_key=key,
                azure_endpoint=os.environ.get("VERSA_ENDPOINT") or DEFAULT_OPENAI_ENDPOINT,
                api_version=os.environ.get("VERSA_API_VERSION") or DEFAULT_OPENAI_API_VERSION,
                timeout=self.timeout_s, max_retries=self.max_retries,
            )
        return self._openai

    # -- calls ---------------------------------------------------------------------------
    def complete(self, model: str, prompt: str, system: str | None = None,
                 max_output_tokens: int | None = None, temperature: float | None = None,
                 extra: dict[str, Any] | None = None) -> VersaResult:
        """One user turn in, one `VersaResult` out. Never raises for API or network errors.

        temperature is sent only when given: recent models on both routes reject or ignore it.
        `extra` is passed through to the SDK call for route-specific options.
        """
        started = time.monotonic()
        try:
            route = route_for(model)
        except VersaConfigError as exc:
            return _error_result("unknown", model, exc, started)
        try:
            if len(prompt) + len(system or "") > MAX_PROMPT_CHARS:
                raise VersaConfigError(f"prompt longer than {MAX_PROMPT_CHARS} characters")
            cap = _bound_tokens(max_output_tokens)
            if route == "anthropic":
                return self._complete_anthropic(model, prompt, system, cap, temperature, extra, started)
            return self._complete_openai(model, prompt, system, cap, temperature, extra, started)
        except Exception as exc:  # noqa: BLE001 - every failure becomes a sanitized result
            return _error_result(route, model, exc, started)

    def _complete_anthropic(self, model, prompt, system, cap, temperature, extra, started) -> VersaResult:
        kwargs: dict[str, Any] = dict(model=model, max_tokens=cap,
                                      messages=[{"role": "user", "content": prompt}])
        if system:
            kwargs["system"] = system
        if temperature is not None:
            kwargs["temperature"] = temperature
        kwargs.update(extra or {})
        resp = self._anthropic_client().messages.create(**kwargs)
        # Select text blocks by type: a response can open with a thinking block.
        text = "".join(getattr(b, "text", "") for b in (getattr(resp, "content", None) or [])
                       if getattr(b, "type", None) == "text")
        text, truncated = _bound_text(text, self.max_chars)
        u = getattr(resp, "usage", None)
        usage = {}
        if u is not None:
            i, o = int(getattr(u, "input_tokens", 0) or 0), int(getattr(u, "output_tokens", 0) or 0)
            usage = {"input_tokens": i, "output_tokens": o, "total_tokens": i + o}
            for extra_name in ("cache_read_input_tokens", "cache_creation_input_tokens"):
                v = getattr(u, extra_name, None)
                if v:
                    usage[extra_name] = int(v)
        stop = getattr(resp, "stop_reason", None)
        ok = bool(text) and stop != "refusal"
        return VersaResult(
            ok=ok, route="anthropic", model_requested=model, model_reported=getattr(resp, "model", None),
            text=text, truncated=truncated, stop_reason=stop, usage=usage,
            latency_s=round(time.monotonic() - started, 3),
            request_id=getattr(resp, "_request_id", None) or getattr(resp, "id", None),
            error_type=None if ok else "EmptyOrRefused",
            error=None if ok else f"no text returned (stop_reason={stop!r})",
        )

    def _complete_openai(self, model, prompt, system, cap, temperature, extra, started) -> VersaResult:
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}]
        kwargs: dict[str, Any] = dict(model=model, messages=messages, max_completion_tokens=cap)
        if temperature is not None:
            kwargs["temperature"] = temperature
        kwargs.update(extra or {})
        resp = self._openai_client().chat.completions.create(**kwargs)
        choice = resp.choices[0] if getattr(resp, "choices", None) else None
        text = (getattr(getattr(choice, "message", None), "content", None) or "") if choice else ""
        text, truncated = _bound_text(text, self.max_chars)
        u = getattr(resp, "usage", None)
        usage = {}
        if u is not None:
            i, o = int(getattr(u, "prompt_tokens", 0) or 0), int(getattr(u, "completion_tokens", 0) or 0)
            usage = {"input_tokens": i, "output_tokens": o, "total_tokens": i + o}
            details = getattr(u, "completion_tokens_details", None)
            r = getattr(details, "reasoning_tokens", None) if details is not None else None
            if r:
                usage["reasoning_tokens"] = int(r)
        stop = getattr(choice, "finish_reason", None) if choice else None
        ok = bool(text)
        return VersaResult(
            ok=ok, route="openai", model_requested=model, model_reported=getattr(resp, "model", None),
            text=text, truncated=truncated, stop_reason=stop, usage=usage,
            latency_s=round(time.monotonic() - started, 3),
            request_id=getattr(resp, "_request_id", None) or getattr(resp, "id", None),
            error_type=None if ok else "EmptyResponse",
            error=None if ok else f"no text returned (finish_reason={stop!r})",
        )

    def health(self, model: str) -> VersaResult:
        """One synthetic call. 1,024 output tokens leaves room for models that think first."""
        return self.complete(model, "Reply with exactly: OK", max_output_tokens=1024)

    def catalog(self) -> dict[str, Any]:
        """Live deployment list from the OpenAI route. No model is invoked.

        The Anthropic route has no listing endpoint that we know of; verify those IDs with health().
        """
        import httpx
        key = os.environ.get("VERSA_API_KEY")
        if not key:
            return {"ok": False, "error": "VERSA_API_KEY is not set"}
        endpoint = (os.environ.get("VERSA_ENDPOINT") or DEFAULT_OPENAI_ENDPOINT).rstrip("/")
        version = os.environ.get("VERSA_API_VERSION") or DEFAULT_OPENAI_API_VERSION
        out: dict[str, Any] = {"ok": False, "endpoint": endpoint, "api_version": version}
        try:
            r = httpx.get(f"{endpoint}/openai/deployments", params={"api-version": version},
                          headers={"api-key": key}, timeout=min(self.timeout_s, 60.0))
            out["status_code"] = r.status_code
            if r.status_code != 200:
                out["error"] = sanitize(r.text)
                return out
            data = r.json()
            rows = data.get("data", data if isinstance(data, list) else [])
            out["deployments"] = sorted(
                ({"id": d.get("id"), "model": d.get("model"), "status": d.get("status")}
                 for d in rows if isinstance(d, dict)), key=lambda d: str(d["id"]))
            out["ok"] = True
        except Exception as exc:  # noqa: BLE001
            out["error_type"], out["error"] = type(exc).__name__, sanitize(exc)
        return out


class VersaCallError(RuntimeError):
    """A failed call from `make_llm_callable`. Carries the sanitized `VersaResult` as `.result`."""

    def __init__(self, result: VersaResult) -> None:
        super().__init__(f"{result.error_type}: {result.error}")
        self.result = result


def make_llm_callable(model: str, system: str | None = None, max_output_tokens: int = 8192,
                      timeout_s: float = DEFAULT_TIMEOUT_S, max_retries: int = 0,
                      max_chars: int = 200_000, effort: str | None = None,
                      log: list[dict[str, Any]] | None = None):
    """`callable(payload_text) -> response_text` for harnesses such as DirectLLMArm.

    No automatic retry by default (max_retries=0), so one call is one billed request.
    Raises VersaCallError (sanitized) on any failure. If `log` is given, every call's result
    (text included, credentials never) is appended to it, for usage and audit.
    `effort` ("low"|"medium"|"high"|"max") is sent as output_config.effort on the anthropic route only.
    """
    route = route_for(model)
    client = VersaClient(timeout_s=timeout_s, max_retries=max_retries, max_chars=max_chars)
    extra = {"output_config": {"effort": effort}} if (effort and route == "anthropic") else None

    def call(payload_text: str) -> str:
        res = client.complete(model, payload_text, system=system,
                              max_output_tokens=max_output_tokens, extra=extra)
        if log is not None:
            log.append(res.to_dict())
        if not res.ok:
            raise VersaCallError(res)
        return res.text

    call.model = model  # type: ignore[attr-defined]
    call.route = route  # type: ignore[attr-defined]
    return call


def _read(path: str | None) -> str | None:
    if path is None:
        return None
    return sys.stdin.read() if path == "-" else Path(path).read_text()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="UCSF Versa client (synthetic or public data only unless cleared).")
    p.add_argument("--env-file", help="KEY=VALUE file to load Versa settings from (values are never printed)")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("models")
    sub.add_parser("catalog")
    h = sub.add_parser("health"); h.add_argument("--model", required=True)
    c = sub.add_parser("call")
    c.add_argument("--model", required=True)
    c.add_argument("--prompt-file", required=True, help="path, or - for stdin")
    c.add_argument("--system-file")
    c.add_argument("--max-output-tokens", type=int, default=DEFAULT_MAX_OUTPUT_TOKENS)
    c.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    c.add_argument("--json", action="store_true", help="print the whole result as JSON")
    a = p.parse_args(argv)

    if a.env_file:
        names = load_env_file(a.env_file)
        print(f"loaded {len(names)} setting(s) from env file: {', '.join(names) or 'none'}", file=sys.stderr)
    if a.cmd == "models":
        print(json.dumps({"anthropic": ANTHROPIC_MODELS, "openai": OPENAI_MODELS}, indent=2))
        return 0
    client = VersaClient(timeout_s=a.timeout, max_chars=getattr(a, "max_chars", DEFAULT_MAX_CHARS))
    if a.cmd == "catalog":
        out = client.catalog()
        print(json.dumps(out, indent=2))
        return 0 if out.get("ok") else 1
    if a.cmd == "health":
        res = client.health(a.model)
        print(json.dumps(res.to_dict(), indent=2))
        return 0 if res.ok else 1
    res = client.complete(a.model, _read(a.prompt_file) or "", system=_read(a.system_file),
                          max_output_tokens=a.max_output_tokens)
    if a.json:
        print(json.dumps(res.to_dict(), indent=2))
    else:
        print(res.text if res.ok else f"ERROR {res.error_type}: {res.error}", file=sys.stdout if res.ok else sys.stderr)
        print(json.dumps({"usage": res.usage, "latency_s": res.latency_s, "stop_reason": res.stop_reason,
                          "model_reported": res.model_reported}), file=sys.stderr)
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
