"""Persistent, deterministic NPC attitudes resolved after Cognee improve()."""

from __future__ import annotations

import json
from pathlib import Path

from event_log import get_all_events


ATTITUDES_FILE = Path(".echoworld_attitudes.json")
NPC_KEYS = ("blacksmith", "merchant", "guard", "elder")
VALID_ATTITUDES = {"warm", "neutral", "suspicious", "hostile"}

DISPLAY_NAMES = {
    "blacksmith": "Gareth",
    "merchant": "Petra",
    "guard": "Mira",
    "elder": "Voss",
}

ATTITUDE_COLORS = {
    "warm": (105, 210, 126),
    "neutral": (210, 214, 216),
    "suspicious": (242, 180, 72),
    "hostile": (232, 83, 76),
}

ATTITUDE_ICONS = {
    "warm": "+",
    "neutral": "=",
    "suspicious": "?",
    "hostile": "!",
}

SCORING_PHRASES = {
    "blacksmith": {
        "positive": ("full price", "without arguing", "fair", "pay", "paid"),
        "negative": ("discount", "cheap", "insult", "ridiculous", "threat"),
    },
    "merchant": {
        "positive": ("buy", "paid", "fair", "polite", "respectful"),
        "negative": (
            "ridiculous",
            "discount",
            "walk away",
            "threat",
            "haggle aggressively",
        ),
    },
}

EVENT_TEXT_FIELDS = (
    "message",
    "player_message",
    "user_message",
    "input",
    "response",
    "npc_response",
    "npc_reply",
    "text",
    "summary",
    "content",
    "description",
)

NPC_ALIASES = {
    "blacksmith": "blacksmith",
    "gareth": "blacksmith",
    "gareth the blacksmith": "blacksmith",
    "merchant": "merchant",
    "petra": "merchant",
    "petra the merchant": "merchant",
    "guard": "guard",
    "mira": "guard",
    "captain mira": "guard",
    "captain mira the guard": "guard",
    "elder": "elder",
    "voss": "elder",
    "elder voss": "elder",
}


def default_attitudes() -> dict[str, str]:
    return {npc_key: "neutral" for npc_key in NPC_KEYS}


def load_attitudes() -> dict[str, str]:
    if not ATTITUDES_FILE.exists():
        return default_attitudes()
    try:
        data = json.loads(ATTITUDES_FILE.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
        return default_attitudes()
    if not isinstance(data, dict):
        return default_attitudes()

    attitudes = default_attitudes()
    for npc_key in NPC_KEYS:
        attitude = data.get(npc_key)
        if isinstance(attitude, str) and attitude in VALID_ATTITUDES:
            attitudes[npc_key] = attitude
    return attitudes


def save_attitudes(attitudes: dict[str, str]) -> None:
    safe_attitudes = default_attitudes()
    for npc_key in NPC_KEYS:
        attitude = attitudes.get(npc_key)
        if attitude in VALID_ATTITUDES:
            safe_attitudes[npc_key] = attitude

    temporary_file = ATTITUDES_FILE.with_suffix(ATTITUDES_FILE.suffix + ".tmp")
    temporary_file.write_text(
        json.dumps(safe_attitudes, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_file.replace(ATTITUDES_FILE)


def reset_attitudes() -> None:
    save_attitudes(default_attitudes())


def get_attitude(npc_key: str) -> str:
    return load_attitudes().get(npc_key, "neutral")


def set_attitude(npc_key: str, attitude: str) -> None:
    if npc_key not in NPC_KEYS or attitude not in VALID_ATTITUDES:
        return
    attitudes = load_attitudes()
    attitudes[npc_key] = attitude
    save_attitudes(attitudes)


def get_attitude_color(attitude: str) -> tuple[int, int, int]:
    return ATTITUDE_COLORS.get(attitude, ATTITUDE_COLORS["neutral"])


def get_attitude_icon(attitude: str) -> str:
    return ATTITUDE_ICONS.get(attitude, ATTITUDE_ICONS["neutral"])


def attitude_summary_text() -> str:
    attitudes = load_attitudes()
    return "\n".join(
        f"{DISPLAY_NAMES[npc_key]}: {attitudes[npc_key]}"
        for npc_key in NPC_KEYS
    )


def _attitude_for_score(score: int) -> str:
    if score >= 3:
        return "warm"
    if score >= 0:
        return "neutral"
    if score <= -4:
        return "hostile"
    return "suspicious"


def _flatten_text_value(
    value: object,
    *,
    depth: int = 0,
    seen: set[int] | None = None,
) -> list[str]:
    """Extract text from a possibly nested JSON-like value without recursing forever."""
    if value is None or depth > 5:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [str(value)]

    seen = seen if seen is not None else set()
    if isinstance(value, (dict, list, tuple, set)):
        value_id = id(value)
        if value_id in seen:
            return []
        seen.add(value_id)

    if isinstance(value, dict):
        parts: list[str] = []
        for nested_value in value.values():
            parts.extend(
                _flatten_text_value(
                    nested_value,
                    depth=depth + 1,
                    seen=seen,
                )
            )
        return parts
    if isinstance(value, (list, tuple, set)):
        parts = []
        for item in value:
            parts.extend(
                _flatten_text_value(item, depth=depth + 1, seen=seen)
            )
        return parts
    return []


def event_to_text(event: dict) -> str:
    """Return normalized dialogue/content text from a defensive event shape."""
    if not isinstance(event, dict):
        return ""

    parts: list[str] = []
    for field in EVENT_TEXT_FIELDS:
        parts.extend(_flatten_text_value(event.get(field)))
    return " ".join(" ".join(parts).split()).casefold()


def _npc_label(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for field in ("npc_key", "key", "name", "display_name", "id"):
            nested_value = value.get(field)
            if isinstance(nested_value, str) and nested_value.strip():
                return nested_value
    if isinstance(value, (list, tuple)):
        for item in value:
            label = _npc_label(item)
            if label:
                return label
    return ""


def event_npc_key(event: dict) -> str:
    """Resolve common event NPC labels to EchoWorld's canonical NPC key."""
    if not isinstance(event, dict):
        return ""

    for field in ("npc_key", "npc", "character", "target_npc"):
        raw_label = _npc_label(event.get(field))
        normalized = " ".join(
            raw_label.casefold().replace("_", " ").replace("-", " ").split()
        )
        if not normalized:
            continue
        if normalized in NPC_ALIASES:
            return NPC_ALIASES[normalized]

        padded_label = f" {normalized} "
        for alias in sorted(NPC_ALIASES, key=len, reverse=True):
            if f" {alias} " in padded_label:
                return NPC_ALIASES[alias]
    return ""


def _score_standard_npc(npc_key: str, text: str) -> tuple[int, list[str]]:
    phrases = SCORING_PHRASES[npc_key]
    score = 0
    reasons: list[str] = []
    for phrase in phrases["positive"]:
        if phrase in text:
            score += 1
            reasons.append(f"positive: {phrase}")
    for phrase in phrases["negative"]:
        if phrase in text:
            score -= 1
            reasons.append(f"negative: {phrase}")
    return score, reasons


def _score_merchant(text: str) -> tuple[int, list[str]]:
    """Score Petra's bargaining interactions with weighted rude-language signals."""
    if not text:
        return 0, []

    score = 0
    reasons: list[str] = []
    for phrase in ("buy", "paid", "fair", "polite", "respectful"):
        if phrase in text:
            score += 1
            reasons.append(f"positive: {phrase}")

    # Prefer the most specific pricing phrase so "ridiculous" is not counted
    # twice for the same insult.
    if "your prices are ridiculous" in text:
        score -= 3
        reasons.append("prices ridiculous")
    elif "ridiculous" in text:
        score -= 2
        reasons.append("ridiculous")

    # Likewise, treat an explicit discount ultimatum as one strong signal.
    # Less exact wording can still combine a demand and a walk-away threat.
    if "discount or i walk away" in text:
        score -= 3
        reasons.append("discount demand / walk away threat")
    else:
        if "give me a discount" in text:
            score -= 2
            reasons.append("discount demand")
        if "walk away" in text:
            score -= 2
            reasons.append("walk away threat")

    for phrase, reason in (
        ("threat", "threat"),
        ("haggle aggressively", "aggressive haggling"),
    ):
        if phrase in text:
            score -= 2
            reasons.append(reason)
    return score, reasons


def _score_guard(text: str) -> tuple[int, list[str]]:
    if not text:
        return 0, []

    strong_denials = (
        "did not argue",
        "didn't argue",
        "never argued",
        "i did not argue",
        "i didn't argue",
        "perfectly respectful",
    )
    direct_suspicion = (
        "deny",
        "denied",
        "lie",
        "lied",
        "lying",
        "evasive",
        "suspicious",
    )
    petra_deflection = "petra" in text and (
        "argue" in text or "respectful" in text
    )
    has_strong_denial = any(phrase in text for phrase in strong_denials)

    score = 0
    reasons: list[str] = []
    if has_strong_denial or petra_deflection:
        # Treat the cluster as one signal so the demo denial is suspicious,
        # rather than stacking overlapping phrases into a hostile result.
        score -= 2
        reasons.append(
            "denial about Petra" if "petra" in text else "defensive denial"
        )
    elif any(phrase in text for phrase in direct_suspicion):
        score -= 1
        reasons.append("denial or evasive language")

    # "Perfectly respectful" is defensive evidence above, not a positive hit.
    if not (has_strong_denial or petra_deflection):
        for phrase in ("truth", "honest", "confess", "apologize", "respectful"):
            if phrase in text:
                score += 1
                reasons.append(f"positive: {phrase}")
    return score, reasons


def _score_elder(text: str) -> tuple[int, list[str]]:
    if not text:
        return 0, []

    negative = ("hostile", "rude", "threat", "lie", "evasive")
    positive = ("respectful", "help", "truth", "wisdom")
    matched_negative = [phrase for phrase in negative if phrase in text]
    if matched_negative:
        return -2, [f"direct negative: {phrase}" for phrase in matched_negative]

    matched_positive = [phrase for phrase in positive if phrase in text]
    if matched_positive:
        return 2, [f"direct positive: {phrase}" for phrase in matched_positive]
    return 0, []


def _safe_analysis_int(
    analysis: dict,
    field: str,
    minimum: int,
    maximum: int,
) -> int:
    value = analysis.get(field)
    if isinstance(value, bool):
        return 0
    try:
        numeric_value = int(value)
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(minimum, min(maximum, numeric_value))


def _analysis_tags(analysis: dict) -> set[str]:
    raw_tags = analysis.get("tags")
    if not isinstance(raw_tags, (list, tuple, set)):
        return set()
    return {
        str(tag).casefold().strip()
        for tag in raw_tags
        if str(tag).strip()
    }


def _safe_analysis_bool(analysis: dict, field: str) -> bool:
    value = analysis.get(field)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.casefold().strip() in {"true", "yes", "1"}
    return False


def _blacksmith_insult_reasons(event_text: str) -> list[str]:
    phrases = {
        "your swords are bad": "bad swords",
        "swords are bad": "bad swords",
        "bad swords": "bad swords",
        "do better": "direct disrespect",
        "poor work": "poor work",
        "terrible work": "terrible work",
        "bad work": "bad work",
        "your craft is bad": "insulted craft",
    }
    return list(
        dict.fromkeys(
            reason
            for phrase, reason in phrases.items()
            if phrase in event_text
        )
    )


def _score_structured_analysis(
    npc_key: str,
    analysis: dict,
) -> tuple[int, list[str]]:
    """Score one direct interaction from semantic analysis metadata."""
    tags = _analysis_tags(analysis)
    trust_delta = _safe_analysis_int(analysis, "trust_delta", -3, 3)
    threat_level = _safe_analysis_int(analysis, "threat_level", 0, 3)
    hostility_level = _safe_analysis_int(
        analysis,
        "hostility_level",
        0,
        3,
    )
    is_ultimatum = _safe_analysis_bool(analysis, "is_ultimatum")
    is_threat = _safe_analysis_bool(analysis, "is_threat")
    is_coercive = _safe_analysis_bool(analysis, "is_coercive")
    tone = str(analysis.get("tone") or "neutral").casefold().strip()
    honesty = str(
        analysis.get("honesty_signal") or "unknown"
    ).casefold().strip()
    truth_risk = bool(
        tags.intersection(
            {
                "possible_lie",
                "denial",
                "guard_suspicion",
                "contradiction",
                "contradictions",
                "uncertain",
                "uncertainty",
            }
        )
        or honesty in {"dishonest", "evasive"}
    )
    explicit_hostility = bool(
        tone in {"rude", "aggressive"}
        or is_ultimatum
        or is_coercive
        or is_threat
        or tags.intersection(
            {
                "insult",
                "direct_disrespect",
                "rude_criticism",
                "threat",
            }
        )
        or (npc_key == "guard" and "bribe_attempt" in tags)
    )
    direct_hostility = bool(
        explicit_hostility or (hostility_level >= 2 and not truth_risk)
    )

    score = trust_delta
    reasons: list[str] = [f"trust_delta={trust_delta}"]

    if hostility_level >= 3:
        score -= 2
        reasons.append("hostility_level=3")
    elif hostility_level == 2:
        score -= 1
        reasons.append("hostility_level=2")
    if is_ultimatum:
        score -= 1
        reasons.append("ultimatum")
    if is_coercive:
        score -= 1
        reasons.append("coercive")
    if is_threat:
        score -= 1
        reasons.append("semantic threat")
    if threat_level >= 2:
        score -= 1
        reasons.append(f"threat_level={threat_level}")
    for matched_tone, modifier in (
        ("aggressive", -1),
        ("rude", -1),
        ("friendly", 1),
        ("respectful", 1),
    ):
        if tone == matched_tone:
            score += modifier
            reasons.append(f"tone={matched_tone}")

    if honesty == "honest":
        score += 1
        reasons.append("honesty=honest")
    elif honesty == "dishonest":
        score -= 2
        reasons.append("honesty=dishonest")
    elif honesty == "evasive":
        score -= 1
        reasons.append("honesty=evasive")

    if npc_key == "blacksmith":
        for tag, modifier in (
            ("fair_trade", 2),
            ("blacksmith_fairness", 1),
            ("insult", -2),
            ("threat", -2),
        ):
            if tag in tags:
                score += modifier
                reasons.append(tag)
        if (
            "purchase_interest" in tags
            and tone == "respectful"
        ):
            score += 1
            reasons.append("respectful purchase")
    elif npc_key == "merchant":
        if "fair_trade" in tags:
            score += 1
            reasons.append("fair_trade")
        if (
            "purchase_interest" in tags
            and tone in {"respectful", "neutral"}
        ):
            score += 1
            reasons.append("respectful purchase interest")
        if hostility_level >= 3 and is_ultimatum:
            score = min(score, -4)
            reasons.append("forced=hostile")
        if {"aggressive_bargain", "threat"} <= tags:
            score = min(score, -4)
            reasons.extend(("aggressive_bargain", "threat", "forced=hostile"))
    elif npc_key == "guard":
        denial_cluster = tags.intersection(
            {"possible_lie", "denial", "guard_suspicion"}
        )
        if denial_cluster:
            score -= 1
            reasons.extend(sorted(denial_cluster))
        if "honest_confession" in tags:
            score += 2
            reasons.append("honest_confession")
        if "respectful" in tags:
            score += 1
            reasons.append("respectful")
        if "bribe_attempt" in tags:
            score -= 3
            reasons.append("bribe_attempt")
        if "threat" in tags:
            score -= 2
            reasons.append("threat")
        if "promise_broken" in tags:
            score -= 3
            reasons.append("promise_broken")
        if "trust_breach" in tags:
            score -= 2
            reasons.append("trust_breach")

        # A single non-threatening denial is suspicious, not automatically
        # hostile, even when multiple semantic fields describe that denial.
        if (
            denial_cluster
            and threat_level < 2
            and "threat" not in tags
            and "bribe_attempt" not in tags
            and tone != "aggressive"
            and score < -3
        ):
            score = -3
            reasons.append("single-denial cap")
    elif npc_key == "elder":
        for tag, modifier in (
            ("honest_confession", 1),
            ("respectful", 1),
            ("threat", -1),
            ("insult", -1),
            ("possible_lie", -1),
        ):
            if tag in tags:
                score += modifier
                reasons.append(tag)

    # Truth uncertainty maps to suspicious; direct aggression maps to hostile.
    if direct_hostility:
        score = min(score, -4)
        reasons.append("forced=hostile")
    elif truth_risk and score < -3:
        score = -3
        reasons.append("truth-risk cap=suspicious")
    return score, reasons


def resolve_attitudes_after_improve(run_id: str) -> list[str]:
    previous = load_attitudes()
    scores = {npc_key: 0 for npc_key in NPC_KEYS}
    reasons = {npc_key: [] for npc_key in NPC_KEYS}
    fallback_texts = {npc_key: [] for npc_key in NPC_KEYS}

    for event in get_all_events():
        if not isinstance(event, dict):
            continue
        session_id = str(event.get("session_id") or "")
        if not session_id or not session_id.startswith(run_id):
            continue
        npc_key = event_npc_key(event)
        if npc_key not in scores:
            continue

        analysis = event.get("analysis")
        if isinstance(analysis, dict) and analysis:
            event_score, event_reasons = _score_structured_analysis(
                npc_key,
                analysis,
            )
            if npc_key == "blacksmith":
                craft_insults = _blacksmith_insult_reasons(
                    event_to_text(event)
                )
                if craft_insults:
                    event_score = min(event_score, -4)
                    event_reasons.extend(
                        ["insult", *craft_insults, "forced=hostile"]
                    )
            scores[npc_key] += event_score
            reasons[npc_key].extend(event_reasons)
            continue

        # Backward compatibility for event rows created before analysis v1.
        event_text = event_to_text(event)
        if event_text:
            fallback_texts[npc_key].append(event_text)

    for npc_key in NPC_KEYS:
        fallback_text = " ".join(fallback_texts[npc_key])
        if not fallback_text:
            continue
        if npc_key == "blacksmith":
            fallback_score, fallback_reasons = _score_standard_npc(
                npc_key,
                fallback_text,
            )
            if npc_key == "blacksmith":
                craft_insults = _blacksmith_insult_reasons(fallback_text)
                if craft_insults:
                    fallback_score = min(fallback_score, -4)
                    fallback_reasons.extend(
                        ["insult", *craft_insults, "forced=hostile"]
                    )
        elif npc_key == "merchant":
            fallback_score, fallback_reasons = _score_merchant(fallback_text)
        elif npc_key == "guard":
            fallback_score, fallback_reasons = _score_guard(fallback_text)
        else:
            # Voss still uses direct Elder events only; no other NPC's text is
            # admitted into this per-NPC fallback bucket.
            fallback_score, fallback_reasons = _score_elder(fallback_text)
        scores[npc_key] += fallback_score
        reasons[npc_key].extend(
            f"legacy: {reason}" for reason in fallback_reasons
        )

    for npc_key in NPC_KEYS:
        debug_reasons = list(dict.fromkeys(reasons[npc_key]))
        forced_attitude = (
            "hostile" if "forced=hostile" in debug_reasons else "none"
        )
        resolved_attitude = _attitude_for_score(scores[npc_key])
        print(
            f"[attitude] {npc_key} score={scores[npc_key]} "
            f"forced={forced_attitude} "
            f"resolved={resolved_attitude} "
            f"reasons={debug_reasons!r}"
        )

    resolved = {
        npc_key: _attitude_for_score(scores[npc_key])
        for npc_key in NPC_KEYS
    }
    save_attitudes(resolved)

    report = []
    for npc_key in NPC_KEYS:
        name = DISPLAY_NAMES[npc_key]
        old_attitude = previous[npc_key]
        new_attitude = resolved[npc_key]
        if old_attitude == new_attitude:
            report.append(f"{name}: remains {new_attitude}")
        else:
            report.append(f"{name}: {old_attitude} → {new_attitude}")
    return report


if __name__ == "__main__":
    merchant_test_text = (
        "Your prices are ridiculous. Give me a discount or I walk away."
    ).casefold()
    merchant_test_score, merchant_test_reasons = _score_merchant(
        merchant_test_text
    )
    merchant_test_attitude = _attitude_for_score(merchant_test_score)
    print(
        f"[attitude] merchant score={merchant_test_score} "
        f"reasons={merchant_test_reasons!r}"
    )
    print("Expected: hostile")
    print(f"Actual: {merchant_test_attitude}")
    assert merchant_test_attitude == "hostile"
