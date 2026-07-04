"""Persistent verified promise state for EchoWorld's consequence mechanics."""

from __future__ import annotations

import json
from pathlib import Path


PROMISES_FILE = Path(".echoworld_promises.json")
MIRA_PROMISE_KEY = "mira_no_trouble"


def default_promises() -> dict:
    return {
        MIRA_PROMISE_KEY: {
            "status": "not_made",
            "made_to": "guard",
            "promise_text": "Player promised Captain Mira not to cause trouble.",
            "made_day": None,
            "made_session_id": None,
            "broken": False,
            "broken_day": None,
            "broken_session_id": None,
            "broken_with_npc": None,
            "broken_summary": None,
            "callout_pending": False,
            "callout_delivered": False,
        }
    }


def load_promises() -> dict:
    defaults = default_promises()
    if not PROMISES_FILE.exists():
        return defaults
    try:
        loaded = json.loads(PROMISES_FILE.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
        return defaults
    if not isinstance(loaded, dict):
        return defaults

    loaded_promise = loaded.get(MIRA_PROMISE_KEY)
    if not isinstance(loaded_promise, dict):
        return defaults
    promise = defaults[MIRA_PROMISE_KEY]
    for field in promise:
        if field in loaded_promise:
            promise[field] = loaded_promise[field]
    if promise.get("status") not in {"not_made", "active", "broken"}:
        promise["status"] = "not_made"
    promise["broken"] = bool(promise.get("broken"))
    promise["callout_pending"] = bool(promise.get("callout_pending"))
    promise["callout_delivered"] = bool(promise.get("callout_delivered"))
    return defaults


def save_promises(promises: dict) -> None:
    defaults = default_promises()
    supplied = promises.get(MIRA_PROMISE_KEY) if isinstance(promises, dict) else None
    if isinstance(supplied, dict):
        defaults[MIRA_PROMISE_KEY].update(
            {
                field: supplied[field]
                for field in defaults[MIRA_PROMISE_KEY]
                if field in supplied
            }
        )
    temporary_file = PROMISES_FILE.with_suffix(PROMISES_FILE.suffix + ".tmp")
    temporary_file.write_text(
        json.dumps(defaults, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_file.replace(PROMISES_FILE)


def reset_promises() -> None:
    save_promises(default_promises())


def make_mira_no_trouble_promise(day: int, session_id: str) -> dict:
    promises = load_promises()
    promise = promises[MIRA_PROMISE_KEY]
    promise.update(
        {
            "status": "active",
            "made_day": int(day),
            "made_session_id": str(session_id),
            "broken": False,
            "broken_day": None,
            "broken_session_id": None,
            "broken_with_npc": None,
            "broken_summary": None,
            "callout_pending": False,
            "callout_delivered": False,
        }
    )
    save_promises(promises)
    return dict(promise)


def get_mira_no_trouble_promise() -> dict:
    return dict(load_promises()[MIRA_PROMISE_KEY])


def _analysis_tags(analysis: dict) -> set[str]:
    raw_tags = analysis.get("tags") if isinstance(analysis, dict) else None
    if not isinstance(raw_tags, (list, tuple, set)):
        return set()
    return {
        str(tag).casefold().strip()
        for tag in raw_tags
        if str(tag).strip()
    }


def _analysis_bool(analysis: dict, field: str) -> bool:
    value = analysis.get(field)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.casefold().strip() in {"true", "yes", "1"}
    return False


def _analysis_int(analysis: dict, field: str) -> int:
    value = analysis.get(field)
    if isinstance(value, bool):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return 0


def should_break_mira_promise(
    npc_key: str,
    analysis: dict,
    player_message: str,
) -> bool:
    del player_message  # Structured analysis is the authoritative signal.
    safe_analysis = analysis if isinstance(analysis, dict) else {}
    tags = _analysis_tags(safe_analysis)
    tone = str(safe_analysis.get("tone") or "neutral").casefold().strip()
    intent = str(safe_analysis.get("intent") or "unknown").casefold().strip()
    hostility_level = _analysis_int(safe_analysis, "hostility_level")
    threat_level = _analysis_int(safe_analysis, "threat_level")
    is_threat = _analysis_bool(safe_analysis, "is_threat")
    is_coercive = _analysis_bool(safe_analysis, "is_coercive")
    is_ultimatum = _analysis_bool(safe_analysis, "is_ultimatum")
    canonical_npc = str(npc_key or "").casefold().strip()

    def decision(should_break: bool, reason: str) -> bool:
        print(
            f"[promise-check] npc={canonical_npc or 'unknown'} "
            f"intent={intent} tone={tone} hostility={hostility_level} "
            f"threat={threat_level} ultimatum={str(is_ultimatum).lower()} "
            f"coercive={str(is_coercive).lower()} "
            f"break={str(should_break).lower()} reason={reason}"
        )
        return should_break

    promise = get_mira_no_trouble_promise()
    if promise.get("status") != "active":
        return decision(False, "promise_not_active")
    if not canonical_npc:
        return decision(False, "missing_npc")

    if (
        intent == "bargain"
        and tone in {"respectful", "neutral", "friendly"}
        and not is_threat
        and not is_coercive
        and not is_ultimatum
        and threat_level == 0
        and hostility_level <= 1
    ):
        return decision(False, "polite_bargain")
    if (
        "honest_confession" in tags
        and tone not in {"rude", "aggressive"}
    ) or (
        intent == "apology"
        and tone in {"neutral", "respectful", "friendly"}
    ):
        return decision(False, "honest_confession_or_apology")

    if is_threat:
        return decision(True, "is_threat")
    if is_coercive:
        return decision(True, "is_coercive")
    if is_ultimatum:
        return decision(True, "is_ultimatum")
    if threat_level >= 2:
        return decision(True, "threat_level")
    if hostility_level >= 3:
        return decision(True, "hostility_level")
    if tone == "aggressive":
        return decision(True, "aggressive_tone")
    if "threat" in tags:
        return decision(True, "threat_tag")
    if "insult" in tags:
        return decision(True, "insult_tag")
    if "bribe_attempt" in tags:
        return decision(True, "bribe_attempt_tag")
    if "aggressive_bargain" in tags and (
        is_ultimatum
        or is_threat
        or is_coercive
        or threat_level >= 2
        or hostility_level >= 3
    ):
        return decision(True, "supported_aggressive_bargain")
    return decision(False, "no_strong_trouble_signal")


def break_mira_no_trouble_promise(
    npc_key: str,
    npc_display_name: str,
    analysis: dict,
    day: int,
    session_id: str,
) -> dict:
    promises = load_promises()
    promise = promises[MIRA_PROMISE_KEY]
    if promise.get("status") != "active":
        return dict(promise)

    safe_analysis = analysis if isinstance(analysis, dict) else {}
    tags = _analysis_tags(safe_analysis)
    canonical_npc = str(npc_key or "").casefold().strip()
    display_names = {
        "merchant": "Petra",
        "blacksmith": "Gareth",
        "guard": "Captain Mira",
        "elder": "Elder Voss",
    }
    display_name = display_names.get(
        canonical_npc,
        " ".join(str(npc_display_name or canonical_npc).split()),
    )
    if canonical_npc == "merchant" and (
        "threat" in tags or _analysis_bool(safe_analysis, "is_threat")
    ):
        broken_summary = "threatened Petra over prices"
    elif canonical_npc == "merchant" and (
        _analysis_bool(safe_analysis, "is_ultimatum")
        or _analysis_bool(safe_analysis, "is_coercive")
    ):
        broken_summary = "gave Petra a coercive ultimatum"
    elif canonical_npc == "merchant" and "insult" in tags:
        broken_summary = "insulted Petra"
    elif canonical_npc == "blacksmith" and "insult" in tags:
        broken_summary = "insulted Gareth's craft"
    elif canonical_npc == "guard" and "bribe_attempt" in tags:
        broken_summary = "tried to bribe Captain Mira"
    elif canonical_npc == "guard" and "threat" in tags:
        broken_summary = "threatened Captain Mira"
    elif "insult" in tags:
        broken_summary = f"insulted {display_name}"
    elif "threat" in tags or _analysis_bool(safe_analysis, "is_threat"):
        broken_summary = f"threatened {display_name}"
    else:
        broken_summary = f"caused trouble with {display_name}"

    promise.update(
        {
            "status": "broken",
            "broken": True,
            "broken_day": int(day),
            "broken_session_id": str(session_id),
            "broken_with_npc": canonical_npc,
            "broken_summary": broken_summary,
            "callout_pending": True,
            "callout_delivered": False,
        }
    )
    save_promises(promises)
    return dict(promise)


def get_promise_context_for_npc(npc_key: str) -> str:
    if str(npc_key or "").casefold().strip() != "guard":
        return ""
    promise = get_mira_no_trouble_promise()
    if promise.get("status") == "active":
        return str(promise.get("promise_text") or "")
    if promise.get("status") == "broken":
        summary = str(promise.get("broken_summary") or "caused trouble")
        promise_text = str(
            promise.get("promise_text")
            or "Player promised Captain Mira not to cause trouble."
        )
        return f"{promise_text} Promise broken: {summary}."
    return ""


def get_pending_mira_callout() -> str:
    promise = get_mira_no_trouble_promise()
    if not promise.get("callout_pending"):
        return ""
    summary = str(promise.get("broken_summary") or "caused trouble")
    return f"Player broke their promise to Captain Mira: {summary}."


def mark_mira_callout_delivered() -> None:
    promises = load_promises()
    promise = promises[MIRA_PROMISE_KEY]
    promise["callout_pending"] = False
    promise["callout_delivered"] = True
    save_promises(promises)


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as temporary_directory:
        PROMISES_FILE = Path(temporary_directory) / "promises.json"
        cases = (
            (
                "Could you reduce the price a little?",
                {
                    "intent": "bargain",
                    "tone": "respectful",
                    "tags": [],
                    "trust_delta": 0,
                    "threat_level": 0,
                    "hostility_level": 0,
                    "is_threat": False,
                    "is_coercive": False,
                    "is_ultimatum": False,
                },
                False,
            ),
            (
                "the prices are ridiculous, reduce them or i leave",
                {
                    "intent": "threat",
                    "tone": "aggressive",
                    "tags": ["aggressive_bargain", "threat"],
                    "threat_level": 3,
                    "hostility_level": 3,
                    "is_threat": True,
                    "is_coercive": True,
                    "is_ultimatum": True,
                },
                True,
            ),
            (
                "give me a discount or you'll regret it",
                {
                    "intent": "threat",
                    "tone": "aggressive",
                    "tags": ["threat"],
                    "threat_level": 3,
                    "hostility_level": 3,
                    "is_threat": True,
                    "is_coercive": True,
                    "is_ultimatum": True,
                },
                True,
            ),
            (
                "I want to buy this at a fair price.",
                {
                    "intent": "purchase",
                    "tone": "respectful",
                    "tags": ["purchase_interest", "fair_trade"],
                    "trust_delta": 2,
                    "threat_level": 0,
                    "hostility_level": 0,
                    "is_threat": False,
                    "is_coercive": False,
                    "is_ultimatum": False,
                },
                False,
            ),
        )
        for message, analysis, expected in cases:
            make_mira_no_trouble_promise(1, "promise_self_test_day_1")
            actual = should_break_mira_promise("merchant", analysis, message)
            print(f"Expected: {expected} | Actual: {actual} | {message}")
            assert actual is expected
        reset_promises()
        reset_state = get_mira_no_trouble_promise()
        assert reset_state["status"] == "not_made"
        assert reset_state["broken"] is False
        assert reset_state["callout_pending"] is False
        assert reset_state["broken_summary"] is None
