"""Backend boundary shared by the desktop and browser EchoWorld frontends.

The direct adapter lazily imports the existing memory engine so importing this
module inside a Pygbag build never pulls Cognee, OpenAI, dotenv, or local state
modules into the browser bundle.
"""

from __future__ import annotations

import importlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


NPC_DISPLAY_NAMES = {
    "blacksmith": "Gareth the Blacksmith",
    "merchant": "Petra the Merchant",
    "guard": "Captain Mira the Guard",
    "elder": "Elder Voss",
}
VALID_NPC_KEYS = frozenset(NPC_DISPLAY_NAMES)


class BackendAdapter(ABC):
    """Small async contract used by the game loop in either runtime."""

    @abstractmethod
    async def talk(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    async def bribe(self, npc_key: str) -> dict[str, Any]: ...

    @abstractmethod
    async def endday(self, session_id: str, run_id: str) -> dict[str, Any]: ...

    @abstractmethod
    async def make_promise(self, day: int, session_id: str) -> dict[str, Any]: ...

    @abstractmethod
    async def reset(self) -> dict[str, Any]: ...

    @abstractmethod
    async def get_promises(self) -> dict[str, Any]: ...

    @abstractmethod
    async def get_events(self) -> dict[str, Any]: ...

    @abstractmethod
    async def get_attitudes(self) -> dict[str, Any]: ...


def _safe_analysis(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_event(event: object) -> dict[str, Any] | None:
    """Return only judge-safe event facts; prompts and secrets never leave."""
    if not isinstance(event, dict):
        return None
    npc_key = str(event.get("npc_key") or "").casefold().strip()
    if npc_key not in VALID_NPC_KEYS:
        return None
    analysis = _safe_analysis(event.get("analysis"))
    return {
        "session_id": str(event.get("session_id") or ""),
        "npc_key": npc_key,
        "npc_name": str(event.get("npc_name") or ""),
        "summary": str(analysis.get("summary") or event.get("summary") or ""),
        "analysis": {
            field: analysis.get(field)
            for field in (
                "intent",
                "tone",
                "tags",
                "sentiment_score",
                "trust_delta",
                "threat_level",
                "hostility_level",
                "honesty_signal",
                "is_ultimatum",
                "is_threat",
                "is_coercive",
                "summary",
            )
            if field in analysis
        },
    }


def _append_promise_event(
    session_id: str,
    event_type: str,
    summary: str,
    tags: list[str],
    trust_delta: int,
    sentiment_score: int,
    hostility_level: int,
    tone: str,
    honesty_signal: str,
    player_message: str,
    npc_reply: str,
) -> None:
    append_event = importlib.import_module("event_log").append_event

    analysis = {
        "event_type": event_type,
        "intent": "promise" if event_type == "promise_made" else "promise_broken",
        "tone": tone,
        "tags": tags,
        "sentiment_score": sentiment_score,
        "trust_delta": trust_delta,
        "threat_level": 0,
        "hostility_level": hostility_level,
        "honesty_signal": honesty_signal,
        "is_ultimatum": False,
        "is_threat": False,
        "is_coercive": False,
        "summary": summary,
    }
    try:
        append_event(
            session_id,
            "guard",
            NPC_DISPLAY_NAMES["guard"],
            player_message,
            npc_reply,
            analysis=analysis,
            analysis_version=2,
        )
    except Exception as exc:
        print(f"[promise] Could not append {event_type} event: {exc}")


class DirectBackendAdapter(BackendAdapter):
    """Desktop/server adapter around the existing EchoWorld engine."""

    async def talk(self, payload: dict[str, Any]) -> dict[str, Any]:
        npc_speak = importlib.import_module("npcs").npc_speak
        promises_module = importlib.import_module("promise_system")
        break_mira_no_trouble_promise = (
            promises_module.break_mira_no_trouble_promise
        )
        get_mira_no_trouble_promise = promises_module.get_mira_no_trouble_promise
        get_pending_mira_callout = promises_module.get_pending_mira_callout
        get_promise_context_for_npc = promises_module.get_promise_context_for_npc
        mark_mira_callout_delivered = promises_module.mark_mira_callout_delivered
        should_break_mira_promise = promises_module.should_break_mira_promise

        npc_key = str(payload.get("npc_key") or "").strip()
        message = str(payload.get("message") or "").strip()
        session_id = str(payload.get("session_id") or "").strip()
        day = int(payload.get("day") or 1)
        if not npc_key or not message or not session_id:
            raise ValueError("npc_key, message, and session_id are required.")

        promise_context = str(payload.get("promise_context") or "")
        forced_callout = str(payload.get("forced_callout") or "")
        if npc_key == "guard":
            promise_context = get_promise_context_for_npc("guard")
            forced_callout = get_pending_mira_callout()

        result = await npc_speak(
            npc_key,
            message,
            session_id,
            allow_hearsay=bool(payload.get("allow_hearsay", True)),
            is_first_meeting=bool(payload.get("is_first_meeting", False)),
            verified_memory=payload.get("verified_memory"),
            memory_forbidden=bool(payload.get("memory_forbidden", False)),
            hearsay_session_id=payload.get("hearsay_session_id"),
            attitude=str(payload.get("attitude") or "neutral"),
            return_trace=True,
            promise_context=promise_context,
            forced_callout=forced_callout,
        )
        if isinstance(result, dict):
            reply = str(result.get("reply") or "")
            recall_trace = _safe_analysis(result.get("recall_trace"))
        else:
            reply = str(result)
            recall_trace = {}

        analysis = _safe_analysis(recall_trace.get("analysis"))
        if not analysis:
            analysis = {
                field: recall_trace.get(field)
                for field in (
                    "intent",
                    "tone",
                    "tags",
                    "sentiment_score",
                    "trust_delta",
                    "threat_level",
                    "hostility_level",
                    "honesty_signal",
                    "is_ultimatum",
                    "is_threat",
                    "is_coercive",
                    "summary",
                )
                if field in recall_trace
            }

        promise_broken_now = False
        if should_break_mira_promise(npc_key, analysis, message):
            broken = break_mira_no_trouble_promise(
                npc_key,
                NPC_DISPLAY_NAMES.get(npc_key, npc_key.title()),
                analysis,
                day,
                session_id,
            )
            broken_summary = str(
                broken.get("broken_summary")
                or f"caused trouble with {NPC_DISPLAY_NAMES.get(npc_key, npc_key)}"
            )
            _append_promise_event(
                session_id,
                "promise_broken",
                f"Player broke Mira's no-trouble promise: {broken_summary}.",
                ["promise_broken", "trust_breach"],
                -3,
                -3,
                3,
                "aggressive",
                "unknown",
                message,
                "Captain Mira has not delivered this callout yet.",
            )
            promise_broken_now = True

        if forced_callout and npc_key == "guard":
            promise = get_mira_no_trouble_promise()
            broken_summary = str(
                promise.get("broken_summary") or "caused trouble in the village"
            )
            recall_trace.update(
                {
                    "promise_broken_summary": broken_summary,
                    "analysis_summary": "broken promise",
                    "tags": ["promise_broken", "trust_breach"],
                    "trust_delta": -3,
                    "hostility_level": 3,
                }
            )
            mark_mira_callout_delivered()

        return {
            "reply": reply,
            "recall_trace": recall_trace,
            "analysis": analysis,
            "promise_broken_now": promise_broken_now,
            "forced_callout_delivered": bool(forced_callout and npc_key == "guard"),
            "promises": {"mira_no_trouble": get_mira_no_trouble_promise()},
        }

    async def bribe(self, npc_key: str) -> dict[str, Any]:
        attitude_module = importlib.import_module("npc_attitudes")
        promises_module = importlib.import_module("promise_system")
        bribe_npc = importlib.import_module("world").bribe_npc

        message = await bribe_npc(npc_key)
        attitude_module.set_attitude(npc_key, "neutral")
        if npc_key == "guard":
            promises_module.reset_promises()
        return {
            "message": str(message),
            "attitudes": attitude_module.load_attitudes(),
            "promises": {
                "mira_no_trouble": promises_module.get_mira_no_trouble_promise()
            },
        }

    async def endday(self, session_id: str, run_id: str) -> dict[str, Any]:
        attitude_module = importlib.import_module("npc_attitudes")
        end_day = importlib.import_module("world").end_day

        await end_day(session_id)
        report = attitude_module.resolve_attitudes_after_improve(run_id)
        return {
            "message": (
                "A new day begins. NPC memories were consolidated and gossip spread."
            ),
            "attitude_report": report,
            "attitudes": attitude_module.load_attitudes(),
        }

    async def make_promise(self, day: int, session_id: str) -> dict[str, Any]:
        make_mira_no_trouble_promise = importlib.import_module(
            "promise_system"
        ).make_mira_no_trouble_promise

        promise = make_mira_no_trouble_promise(day, session_id)
        reply = (
            "Then keep your word. No threats, no coercion, no trouble in my village."
        )
        _append_promise_event(
            session_id,
            "promise_made",
            "Player promised Captain Mira not to cause trouble.",
            ["promise_made", "no_trouble_promise", "respectful"],
            1,
            1,
            0,
            "respectful",
            "honest",
            "I promise not to cause trouble.",
            reply,
        )
        return {"message": reply, "promise": promise, "promises": {"mira_no_trouble": promise}}

    async def reset(self) -> dict[str, Any]:
        attitude_module = importlib.import_module("npc_attitudes")
        promises_module = importlib.import_module("promise_system")
        reset_tutorial = importlib.import_module("tutorial_system").reset_tutorial

        error = ""
        try:
            Path(".echoworld_events.jsonl").unlink(missing_ok=True)
        except OSError as exc:
            error = str(exc)
        attitude_module.reset_attitudes()
        promises_module.reset_promises()
        reset_tutorial()
        message = (
            f"Demo state reset, but the local event log could not be cleared: {error}"
            if error
            else "Demo state reset. For a full memory wipe, use bribe on individual NPCs."
        )
        return {
            "message": message,
            "attitudes": attitude_module.load_attitudes(),
            "promises": {
                "mira_no_trouble": promises_module.get_mira_no_trouble_promise()
            },
        }

    async def get_promises(self) -> dict[str, Any]:
        load_promises = importlib.import_module("promise_system").load_promises

        return {"promises": load_promises()}

    async def get_events(self) -> dict[str, Any]:
        get_all_events = importlib.import_module("event_log").get_all_events

        events = [safe for event in get_all_events() if (safe := _safe_event(event))]
        return {"events": events}

    async def get_attitudes(self) -> dict[str, Any]:
        load_attitudes = importlib.import_module("npc_attitudes").load_attitudes

        return {"attitudes": load_attitudes()}


class HttpBackendAdapter(BackendAdapter):
    """Pygbag adapter using same-origin HTTP; contains no backend imports."""

    async def talk(self, payload: dict[str, Any]) -> dict[str, Any]:
        from web_backend_client import backend_talk

        return await backend_talk(payload)

    async def bribe(self, npc_key: str) -> dict[str, Any]:
        from web_backend_client import backend_bribe

        return await backend_bribe({"npc_key": npc_key})

    async def endday(self, session_id: str, run_id: str) -> dict[str, Any]:
        from web_backend_client import backend_endday

        return await backend_endday({"session_id": session_id, "run_id": run_id})

    async def make_promise(self, day: int, session_id: str) -> dict[str, Any]:
        from web_backend_client import backend_make_mira_promise

        return await backend_make_mira_promise({"day": day, "session_id": session_id})

    async def reset(self) -> dict[str, Any]:
        from web_backend_client import backend_reset

        return await backend_reset()

    async def get_promises(self) -> dict[str, Any]:
        from web_backend_client import backend_get_promises

        return await backend_get_promises()

    async def get_events(self) -> dict[str, Any]:
        from web_backend_client import backend_get_events

        return await backend_get_events()

    async def get_attitudes(self) -> dict[str, Any]:
        from web_backend_client import backend_get_attitudes

        return await backend_get_attitudes()


def create_backend_adapter(browser_mode: bool) -> BackendAdapter:
    return HttpBackendAdapter() if browser_mode else DirectBackendAdapter()
