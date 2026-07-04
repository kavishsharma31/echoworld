from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


EVENT_LOG_FILE = Path(".echoworld_events.jsonl")


def append_event(
    session_id: str,
    npc_key: str,
    npc_name: str,
    player_message: str,
    npc_reply: str,
    analysis: dict | None = None,
    analysis_version: int | None = None,
) -> None:
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "npc_key": npc_key,
        "npc_name": npc_name,
        "player_message": player_message,
        "npc_reply": npc_reply,
    }
    if isinstance(analysis, dict):
        event["analysis"] = analysis
        event["analysis_version"] = analysis_version or 1
    with EVENT_LOG_FILE.open("a", encoding="utf-8") as event_file:
        event_file.write(json.dumps(event, ensure_ascii=False) + "\n")


def get_all_events() -> list[dict]:
    if not EVENT_LOG_FILE.exists():
        return []

    events: list[dict] = []
    try:
        with EVENT_LOG_FILE.open("r", encoding="utf-8") as event_file:
            for line in event_file:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except (json.JSONDecodeError, TypeError):
                    continue
                if isinstance(event, dict):
                    events.append(event)
    except (OSError, UnicodeError):
        return []
    return events


def build_elder_hearsay_from_events(session_id: str | None = None) -> str:
    source_details = (
        ("blacksmith", "Gareth the Blacksmith", "Gareth"),
        ("merchant", "Petra the Merchant", "Petra"),
        ("guard", "Captain Mira", "Mira"),
    )
    source_keys = {source_key for source_key, _, _ in source_details}
    ignored_message_phrases = (
        "do you remember",
        "what have you heard",
        "what do you think",
        "we have not met",
        "remember accusing",
    )
    preferred_story_phrases = {
        "blacksmith": ("buy a sword", "sword"),
        "merchant": ("give me a discount", "prices are ridiculous"),
        "guard": ("did not argue with petra", "respectful in the market"),
    }
    first_meaningful: dict[str, dict] = {}
    preferred_story_events: dict[str, dict] = {}

    for event in get_all_events():
        if session_id is not None and event.get("session_id") != session_id:
            continue
        npc_key = event.get("npc_key")
        if npc_key == "elder" or npc_key not in source_keys:
            continue
        player_message = str(event.get("player_message") or "").strip()
        npc_reply = str(event.get("npc_reply") or "").strip()
        normalized_message = player_message.casefold()
        if not player_message and not npc_reply:
            continue
        if any(
            phrase in normalized_message for phrase in ignored_message_phrases
        ):
            continue
        first_meaningful.setdefault(npc_key, event)
        if npc_key not in preferred_story_events and any(
            phrase in normalized_message
            for phrase in preferred_story_phrases[npc_key]
        ):
            preferred_story_events[npc_key] = event

    hearsay_lines: list[str] = []
    for source_key, speaker_name, reply_name in source_details:
        event = preferred_story_events.get(source_key) or first_meaningful.get(
            source_key
        )
        if event is None:
            continue

        player_message = str(event.get("player_message") or "").strip()
        npc_reply = str(event.get("npc_reply") or "").strip()
        details: list[str] = []
        analysis = event.get("analysis")
        summary = ""
        if isinstance(analysis, dict):
            summary = " ".join(str(analysis.get("summary") or "").split())
        if summary:
            details.append(summary)
        else:
            if player_message:
                suffix = "" if player_message.endswith((".", "!", "?")) else "."
                details.append(f"Player said '{player_message}'{suffix}")
            if npc_reply:
                suffix = "" if npc_reply.endswith((".", "!", "?")) else "."
                details.append(f"{reply_name} replied '{npc_reply}'{suffix}")
        if details:
            hearsay_lines.append(f"- {speaker_name} says: {' '.join(details)}")

    if not hearsay_lines:
        return ""

    return (
        "Secondhand village hearsay for Elder Voss:\n"
        "Elder Voss did not witness these events directly.\n"
        + "\n".join(hearsay_lines)
        + "\n\nIf asked what he thinks of the player, Elder Voss should "
        "mention these as hearsay, not personal experience."
    )


def get_session_events(session_id: str) -> list[dict]:
    if not EVENT_LOG_FILE.exists():
        return []

    events: list[dict] = []
    try:
        with EVENT_LOG_FILE.open("r", encoding="utf-8") as event_file:
            for line in event_file:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except (json.JSONDecodeError, TypeError):
                    continue
                if (
                    isinstance(event, dict)
                    and event.get("session_id") == session_id
                ):
                    events.append(event)
    except (OSError, UnicodeError):
        return []
    return events
