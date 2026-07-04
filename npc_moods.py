"""Deterministic, local mood summaries for the EchoWorld frontends."""

from __future__ import annotations

from dataset_registry import get_dataset_name
from event_log import build_elder_hearsay_from_events, get_all_events


FRIENDLY = "Friendly"
NEUTRAL = "Neutral"
SUSPICIOUS = "Suspicious"
ANGRY = "Angry"
CAUTIOUS = "Cautious"
FORGOTTEN = "Forgotten"

NPC_KEYS = ("blacksmith", "merchant", "guard", "elder")

MOOD_COLORS = {
    FRIENDLY: (105, 210, 126),
    NEUTRAL: (210, 214, 216),
    SUSPICIOUS: (242, 180, 72),
    ANGRY: (232, 83, 76),
    CAUTIOUS: (148, 130, 220),
    FORGOTTEN: (151, 213, 232),
}

MOOD_ICONS = {
    FRIENDLY: "+",
    NEUTRAL: "=",
    SUSPICIOUS: "?",
    ANGRY: "!",
    CAUTIOUS: "~",
    FORGOTTEN: "0",
}

SUMMARY_NAMES = {
    "blacksmith": "Gareth",
    "merchant": "Petra",
    "guard": "Mira",
    "elder": "Elder Voss",
}


def _event_text(event: dict) -> str:
    return " ".join(
        str(event.get(field) or "")
        for field in ("player_message", "npc_reply")
    ).casefold()


def _has_rotated_dataset(npc_key: str) -> bool:
    sentinel_dataset = f"mood_{npc_key}"
    return get_dataset_name(npc_key, sentinel_dataset) != sentinel_dataset


def get_npc_moods() -> dict[str, str]:
    moods = {npc_key: NEUTRAL for npc_key in NPC_KEYS}
    events_by_npc: dict[str, list[dict]] = {npc_key: [] for npc_key in NPC_KEYS}
    forgotten_from_events: set[str] = set()

    for event in get_all_events():
        npc_key = event.get("npc_key")
        if npc_key not in events_by_npc:
            continue
        events_by_npc[npc_key].append(event)
        event_action = str(event.get("action") or "").casefold()
        event_status = str(event.get("memory_status") or "").casefold()
        if event_action in {"bribe", "forget", "forgotten"} or event_status in {
            "forgotten",
            "bribed",
        }:
            forgotten_from_events.add(npc_key)

    blacksmith_text = " ".join(_event_text(event) for event in events_by_npc["blacksmith"])
    if "full price" in blacksmith_text or "without arguing" in blacksmith_text:
        moods["blacksmith"] = FRIENDLY

    merchant_text = " ".join(_event_text(event) for event in events_by_npc["merchant"])
    if any(
        phrase in merchant_text
        for phrase in ("ridiculous", "discount", "walk away", "threat")
    ):
        moods["merchant"] = ANGRY

    guard_text = " ".join(_event_text(event) for event in events_by_npc["guard"])
    if (
        "did not argue with petra" in guard_text
        or "perfectly respectful" in guard_text
    ):
        moods["guard"] = SUSPICIOUS

    if build_elder_hearsay_from_events():
        moods["elder"] = CAUTIOUS

    # A bribe rotates the active dataset; this local signal overrides old events.
    for npc_key in NPC_KEYS:
        if npc_key in forgotten_from_events or _has_rotated_dataset(npc_key):
            moods[npc_key] = FORGOTTEN

    return moods


def get_mood_color(mood: str) -> tuple[int, int, int]:
    return MOOD_COLORS.get(mood, MOOD_COLORS[NEUTRAL])


def get_mood_icon(mood: str) -> str:
    return MOOD_ICONS.get(mood, MOOD_ICONS[NEUTRAL])


def mood_summary_text() -> str:
    moods = get_npc_moods()
    return "\n".join(
        f"{SUMMARY_NAMES[npc_key]}: {moods[npc_key]}"
        for npc_key in NPC_KEYS
    )
