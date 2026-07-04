"""Browser-safe same-origin HTTP client for the EchoWorld Pygbag frontend."""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import platform
import sys


def _default_base_url() -> str:
    configured = os.getenv("ECHOWORLD_API_BASE", "").rstrip("/")
    if configured:
        return configured
    if sys.platform == "emscripten":
        try:
            hostname = str(platform.window.location.hostname)
            port = str(platform.window.location.port)
            if hostname in {"localhost", "127.0.0.1"} and port not in {"", "8787"}:
                return "http://127.0.0.1:8787"
        except Exception:
            pass
    return ""


API_BASE_URL = _default_base_url()
_request_sequence = 0


async def _browser_request(path: str, method: str, payload: dict | None) -> dict:
    """Use Pygbag's platform.window bridge without blocking the WASM loop."""
    bridge_source = r"""
(() => {
  if (window.echoworldApiStart) return;
  window.__echoworldApiResults = Object.create(null);
  window.echoworldApiStart = (id, url, method, body) => {
    const options = {method, headers: {'Content-Type': 'application/json'}};
    if (body) options.body = body;
    fetch(url, options)
      .then(async response => {
        const text = await response.text();
        window.__echoworldApiResults[id] = JSON.stringify({
          ok: response.ok, status: response.status, text
        });
      })
      .catch(error => {
        window.__echoworldApiResults[id] = JSON.stringify({
          ok: false, status: 0, text: String(error)
        });
      });
  };
  window.echoworldApiPoll = id => window.__echoworldApiResults[id] || '';
  window.echoworldApiClear = id => { delete window.__echoworldApiResults[id]; };
})();
"""
    if not getattr(platform.window, "echoworldApiStart", None):
        platform.window.eval(bridge_source)

    global _request_sequence
    _request_sequence += 1
    request_id = f"echo-{int(asyncio.get_running_loop().time() * 1000)}-{_request_sequence}"
    body = json.dumps(payload) if payload is not None else ""
    platform.window.echoworldApiStart(
        request_id,
        f"{API_BASE_URL}{path}",
        method,
        body,
    )
    started = asyncio.get_running_loop().time()
    while True:
        raw_result = str(platform.window.echoworldApiPoll(request_id) or "")
        if raw_result:
            platform.window.echoworldApiClear(request_id)
            result = json.loads(raw_result)
            response_text = str(result.get("text") or "")
            if not result.get("ok"):
                raise RuntimeError(
                    f"EchoWorld API {result.get('status', 0)}: {response_text[:300]}"
                )
            return json.loads(response_text) if response_text else {}
        if asyncio.get_running_loop().time() - started > 180:
            platform.window.echoworldApiClear(request_id)
            raise TimeoutError("EchoWorld API request timed out.")
        await asyncio.sleep(0)


def _desktop_request(path: str, method: str, payload: dict | None) -> dict:
    urllib_error = importlib.import_module("urllib.error")
    urllib_request = importlib.import_module("urllib.request")

    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib_request.Request(
        f"{API_BASE_URL or 'http://127.0.0.1:8787'}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib_request.urlopen(request, timeout=180) as response:
            response_text = response.read().decode("utf-8")
    except urllib_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"EchoWorld API {exc.code}: {detail[:300]}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"EchoWorld API unavailable: {exc.reason}") from exc
    return json.loads(response_text) if response_text else {}


async def _request(path: str, method: str = "GET", payload: dict | None = None) -> dict:
    if sys.platform == "emscripten":
        return await _browser_request(path, method, payload)
    return await asyncio.to_thread(_desktop_request, path, method, payload)


async def backend_health() -> dict:
    return await _request("/api/health")


async def backend_talk(payload: dict) -> dict:
    return await _request("/api/talk", "POST", payload)


async def backend_bribe(payload: dict) -> dict:
    return await _request("/api/bribe", "POST", payload)


async def backend_endday(payload: dict) -> dict:
    return await _request("/api/endday", "POST", payload)


async def backend_reset() -> dict:
    return await _request("/api/reset", "POST", {})


async def backend_make_mira_promise(payload: dict) -> dict:
    return await _request("/api/promise/mira-no-trouble", "POST", payload)


async def backend_get_promises() -> dict:
    return await _request("/api/promises")


async def backend_get_events() -> dict:
    return await _request("/api/events")


async def backend_get_attitudes() -> dict:
    return await _request("/api/attitudes")
