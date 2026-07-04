"""Semantic interaction classification with a deterministic offline fallback."""

from __future__ import annotations

import json
import os
import re

from openai import AsyncOpenAI


ALLOWED_INTENTS = {
    "greeting",
    "purchase",
    "bargain",
    "threat",
    "lie",
    "confession",
    "apology",
    "help_request",
    "question",
    "bribe",
    "unknown",
}
ALLOWED_TONES = {
    "respectful",
    "neutral",
    "rude",
    "aggressive",
    "evasive",
    "friendly",
}
ALLOWED_HONESTY_SIGNALS = {"honest", "dishonest", "evasive", "unknown"}


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def _normalized_message(message: str) -> str:
    return " ".join(
        str(message or "")
        .casefold()
        .replace("’", "'")
        .replace("\n", " ")
        .split()
    )


def _detect_topics(text: str) -> list[str]:
    topic_phrases = {
        "sword": ("sword", "blade", "steel", "weapon"),
        "trade": ("buy", "purchase", "pay", "paid", "coin", "price"),
        "bargaining": ("discount", "bargain", "haggle", "lower"),
        "petra": ("petra",),
        "gossip": ("gossip", "rumor", "rumour", "story", "heard"),
        "village": ("village", "echoworld"),
        "memory": ("remember", "memory", "forget"),
        "help": ("help", "assist"),
        "bribe": ("bribe", "look the other way", "keep quiet"),
    }
    return [
        topic
        for topic, phrases in topic_phrases.items()
        if _contains_any(text, phrases)
    ]


def analyze_interaction_fallback(
    npc_key: str,
    player_message: str,
    npc_reply: str | None = None,
) -> dict:
    """Analyze only the player's current message into structured gameplay facts."""
    del npc_reply  # Replies must not change facts inferred from the player message.

    npc = str(npc_key or "").casefold().strip()
    text = _normalized_message(player_message)
    tags: set[str] = set()
    sentiment_score = 0
    trust_delta = 0
    threat_level = 0

    greeting = bool(
        re.search(r"\b(hello|hi|hey|greetings|good morning|good evening)\b", text)
    )
    purchase = _contains_any(
        text,
        ("buy", "purchase", "pay", "paid", "full price", "looking for"),
    )
    price_complaint = _contains_any(
        text,
        (
            "prices are ridiculous",
            "price is ridiculous",
            "prices are insane",
            "price is insane",
            "too expensive",
            "pricey",
        ),
    )
    reduction_request = _contains_any(
        text,
        (
            "reduce them",
            "lower them",
            "lower the price",
            "lower your price",
            "reduce the price",
            "reduce your price",
            "reduce price",
            "reduce it",
            "reduce this",
            "lower it",
            "give me a discount",
            "discount",
        ),
    )
    bargain = price_complaint or reduction_request or _contains_any(
        text,
        ("bargain", "haggle", "cheaper"),
    )
    fair_trade = _contains_any(
        text,
        ("full price", "fair price", "pay fairly", "paid fairly", "without arguing", "no arguing"),
    )
    apology = _contains_any(
        text,
        ("i am sorry", "i'm sorry", "i apologize", "i apologise", "forgive me", "my apology"),
    )
    confession = _contains_any(
        text,
        (
            "i need to confess",
            "confession:",
            "i confess",
            "i lied",
            "i was lying",
            "i am sorry i lied",
            "i admit",
            "truth is",
            "the truth is",
        ),
    )
    denial = _contains_any(
        text,
        ("i did not", "i didn't", "i never", "never argued", "not me", "i deny", "didn't happen"),
    )
    accusation_context = _contains_any(
        text,
        ("argue", "accus", "petra", "steal", "stole", "take", "took", "blame"),
    )
    bribe_attempt = _contains_any(
        text,
        ("bribe", "coin to forget", "forget this happened", "look the other way", "keep quiet"),
    )
    help_request = _contains_any(
        text,
        ("help me", "can you help", "could you help", "need help", "assist me"),
    )
    question = "?" in str(player_message or "") or bool(
        re.match(r"^(what|why|where|when|who|how|do|does|did|can|could|would|will|are|is)\b", text)
    )
    friendly_language = greeting or _contains_any(
        text,
        ("friend", "glad to meet", "nice to meet", "share a story", "good to see"),
    )
    respectful_language = _contains_any(
        text,
        ("please", "thank you", "thanks", "respectfully", "with respect", "full price", "fair price"),
    )
    rude_language = _contains_any(
        text,
        (
            "ridiculous",
            "insane",
            "stupid",
            "idiot",
            "fool",
            "rip-off",
            "ripoff",
            "useless",
            "trash",
            "garbage",
        ),
    )
    leaving_ultimatum = _contains_any(
        text,
        (
            "walk away",
            "i'll walk away",
            "i am leaving",
            "i'm leaving",
            "i leave",
            "or i leave",
            "or i'll leave",
            "or i will leave",
            "or i walk away",
            "or i'll walk away",
            "lower them or",
            "reduce them or",
            "discount or",
        ),
    )
    violent_threat = _contains_any(
        text,
        ("hurt you", "kill", "attack", "burn this", "break your", "you'll regret", "you will regret"),
    )
    explicit_threat = (
        violent_threat
        or "or else" in text
        or "threat" in text
        or _contains_any(text, ("cause trouble", "make trouble", "start trouble"))
    )
    polite_reduction_request = (
        bargain
        and question
        and _contains_any(
            text,
            (
                "can you",
                "could you",
                "could we",
                "would you",
                "please",
                "is there any discount",
            ),
        )
        and not rude_language
        and not leaving_ultimatum
        and not explicit_threat
    )
    price_leave_ultimatum = (
        (price_complaint or reduction_request) and leaving_ultimatum
    )
    forceful_price_bargain = (
        (price_complaint or reduction_request)
        and not polite_reduction_request
        and not price_leave_ultimatum
        and not explicit_threat
    )
    aggressive_bargain = price_leave_ultimatum or (
        bargain and explicit_threat
    )
    rude_bargain = bargain and (
        rude_language or aggressive_bargain or forceful_price_bargain
    )

    if purchase:
        tags.add("purchase_interest")
    if fair_trade:
        tags.add("fair_trade")
        sentiment_score += 2
        trust_delta += 2
        if npc == "blacksmith":
            tags.add("blacksmith_fairness")
            trust_delta += 1
    if friendly_language:
        tags.add("friendly")
        sentiment_score += 1
        trust_delta += 1
    if respectful_language and not denial:
        tags.add("respectful")
        sentiment_score += 1
        trust_delta += 1
    if apology:
        tags.add("apology")
        sentiment_score += 1
        trust_delta += 1
    if confession:
        tags.add("honest_confession")
        sentiment_score += 1
        trust_delta += 2 if npc in {"guard", "elder"} else 1
    if rude_language:
        tags.add("insult")
        sentiment_score -= 1
        trust_delta -= 1
    if rude_bargain:
        tags.add("rude_bargaining")
        sentiment_score -= 1
        trust_delta -= 2
    if aggressive_bargain:
        tags.update({"aggressive_bargain", "threat"})
        sentiment_score -= 2
        trust_delta -= 3
        threat_level = max(threat_level, 2)
    elif explicit_threat:
        tags.add("threat")
        sentiment_score -= 3
        trust_delta -= 3
        threat_level = max(threat_level, 3 if violent_threat else 2)
    if price_leave_ultimatum:
        tags.update({"rude_bargaining", "aggressive_bargain", "threat"})
        if npc == "merchant":
            tags.add("merchant_conflict")
        sentiment_score = -3
        trust_delta = -3
        threat_level = 3
    elif forceful_price_bargain:
        tags.update({"rude_bargaining", "aggressive_bargain"})
        sentiment_score = -2
        trust_delta = -2
        threat_level = 1
    if denial and accusation_context:
        tags.add("denial")
        trust_delta -= 1
        if npc == "guard":
            tags.update({"possible_lie", "guard_suspicion"})
            trust_delta -= 1
    if bribe_attempt:
        tags.add("bribe_attempt")
        trust_delta -= 3 if npc == "guard" else 2
        sentiment_score -= 2
    if npc == "merchant" and (rude_bargain or aggressive_bargain or explicit_threat):
        tags.add("merchant_conflict")
    if npc == "elder" and question:
        tags.add("elder_question")

    if confession:
        honesty_signal = "honest"
    elif denial and accusation_context:
        honesty_signal = "evasive"
    elif _contains_any(text, ("i am lying", "i'm lying", "this is a lie")):
        honesty_signal = "dishonest"
        tags.add("possible_lie")
    elif _contains_any(text, ("honestly", "truthfully", "i am telling the truth")):
        honesty_signal = "honest"
    else:
        honesty_signal = "unknown"

    if aggressive_bargain or explicit_threat:
        tone = "aggressive"
    elif denial and accusation_context:
        tone = "evasive"
    elif rude_language or rude_bargain:
        tone = "rude"
    elif friendly_language:
        tone = "friendly"
    elif respectful_language or apology:
        tone = "respectful"
    else:
        tone = "neutral"

    if bribe_attempt:
        intent = "bribe"
    elif confession:
        intent = "confession"
    elif price_leave_ultimatum:
        intent = "threat"
    elif aggressive_bargain or bargain:
        intent = "bargain"
    elif explicit_threat:
        intent = "threat"
    elif denial and accusation_context:
        intent = "lie"
    elif apology:
        intent = "apology"
    elif purchase:
        intent = "purchase"
    elif help_request:
        intent = "help_request"
    elif question:
        intent = "question"
    elif greeting:
        intent = "greeting"
    else:
        intent = "unknown"

    confessed_lie = _contains_any(text, ("i lied", "i was lying", "i am sorry i lied"))
    if confession and apology:
        summary = (
            "Player admitted lying earlier and apologized."
            if confessed_lie
            else "Player made an honest confession and apologized."
        )
    elif confession:
        summary = (
            "Player confessed to an earlier lie."
            if confessed_lie
            else "Player made an honest confession."
        )
    elif apology:
        summary = "Player apologized."
    elif price_leave_ultimatum:
        summary = "Player bargained aggressively and threatened to leave."
    elif forceful_price_bargain:
        summary = "Player bargained aggressively over the price."
    elif polite_reduction_request:
        summary = "Player politely asked for a lower price."
    elif fair_trade:
        summary = "Player offered fair payment."
    elif aggressive_bargain:
        summary = "Player bargained aggressively and made a threat."
    elif explicit_threat:
        summary = "Player made a threat."
    elif denial and "petra" in text and "argue" in text:
        summary = "Player denied arguing with Petra in a way that may sound evasive."
    elif denial:
        summary = "Player denied an accusation in a way that may sound evasive."
    elif bribe_attempt:
        summary = "Player attempted a bribe."
    elif purchase and "sword" in _detect_topics(text):
        summary = "Player expressed interest in buying a sword."
    elif purchase:
        summary = "Player expressed interest in making a purchase."
    elif help_request:
        summary = "Player asked for help."
    elif question:
        summary = "Player asked a neutral question."
    elif greeting:
        summary = "Player offered a greeting."
    elif friendly_language:
        summary = "Player spoke in a friendly manner."
    elif respectful_language:
        summary = "Player spoke respectfully."
    else:
        summary = "Player made a neutral statement."

    is_ultimatum = price_leave_ultimatum or (
        "or else" in text and (bargain or explicit_threat)
    )
    is_threat = bool(explicit_threat or price_leave_ultimatum)
    is_coercive = bool(
        is_ultimatum
        or explicit_threat
        or forceful_price_bargain
        or bribe_attempt
    )
    if price_leave_ultimatum or violent_threat:
        hostility_level = 3
    elif explicit_threat or forceful_price_bargain or aggressive_bargain:
        hostility_level = 2
    elif rude_language or denial or bribe_attempt:
        hostility_level = 1
    else:
        hostility_level = 0
    if price_leave_ultimatum:
        confidence = 0.98
    elif explicit_threat or confession or denial or fair_trade:
        confidence = 0.88
    elif bargain or purchase or apology:
        confidence = 0.78
    else:
        confidence = 0.62

    analysis = {
        "intent": intent if intent in ALLOWED_INTENTS else "unknown",
        "tone": tone if tone in ALLOWED_TONES else "neutral",
        "tags": sorted(tags),
        "sentiment_score": _clamp(sentiment_score, -3, 3),
        "trust_delta": _clamp(trust_delta, -3, 3),
        "threat_level": _clamp(threat_level, 0, 3),
        "honesty_signal": (
            honesty_signal
            if honesty_signal in ALLOWED_HONESTY_SIGNALS
            else "unknown"
        ),
        "topics": _detect_topics(text),
        "summary": summary,
        "hostility_level": hostility_level,
        "is_ultimatum": is_ultimatum,
        "is_threat": is_threat,
        "is_coercive": is_coercive,
        "confidence": confidence,
        "analyzer_source": "fallback",
    }
    return analysis


def analyze_interaction(
    npc_key: str,
    player_message: str,
    npc_reply: str | None = None,
) -> dict:
    """Backward-compatible synchronous entry point for the offline fallback."""
    return analyze_interaction_fallback(npc_key, player_message, npc_reply)


def _semantic_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.casefold().strip()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return default


def _semantic_int(
    value: object,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return _clamp(parsed, minimum, maximum)


def _semantic_confidence(value: object, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(0.0, min(1.0, parsed))


def _string_list(value: object, fallback: list[str]) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return list(fallback)
    cleaned = []
    for item in value:
        normalized = str(item).casefold().strip().replace(" ", "_")
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned


def _normalize_semantic_result(
    raw_result: dict,
    fallback: dict,
    npc_key: str,
) -> dict:
    intent = str(raw_result.get("intent") or "").casefold().strip()
    if intent not in ALLOWED_INTENTS:
        intent = fallback["intent"]
    tone = str(raw_result.get("tone") or "").casefold().strip()
    if tone not in ALLOWED_TONES:
        tone = fallback["tone"]
    honesty = str(
        raw_result.get("honesty_signal") or ""
    ).casefold().strip()
    if honesty not in ALLOWED_HONESTY_SIGNALS:
        honesty = fallback["honesty_signal"]

    tags = _string_list(raw_result.get("tags"), fallback["tags"])
    topics = _string_list(raw_result.get("topics"), fallback["topics"])
    is_ultimatum = _semantic_bool(
        raw_result.get("is_ultimatum"),
        fallback["is_ultimatum"],
    ) or bool(fallback["is_ultimatum"])
    is_threat = _semantic_bool(
        raw_result.get("is_threat"),
        fallback["is_threat"],
    ) or bool(fallback["is_threat"])
    is_coercive = _semantic_bool(
        raw_result.get("is_coercive"),
        fallback["is_coercive"],
    ) or bool(fallback["is_coercive"])
    hostility_level = max(
        _semantic_int(
            raw_result.get("hostility_level"),
            fallback["hostility_level"],
            0,
            3,
        ),
        int(fallback["hostility_level"]),
    )
    trust_delta = _semantic_int(
        raw_result.get("trust_delta"),
        fallback["trust_delta"],
        -3,
        3,
    )
    threat_level = _semantic_int(
        raw_result.get("threat_level"),
        fallback["threat_level"],
        0,
        3,
    )

    fallback_is_polite_bargain = bool(
        fallback.get("intent") == "bargain"
        and fallback.get("tone") in {"respectful", "neutral", "friendly"}
        and not fallback.get("is_ultimatum")
        and not fallback.get("is_threat")
        and not fallback.get("is_coercive")
        and int(fallback.get("threat_level") or 0) == 0
        and int(fallback.get("hostility_level") or 0) <= 1
    )
    if fallback_is_polite_bargain:
        intent = "bargain"
        tone = fallback["tone"]
        is_ultimatum = False
        is_threat = False
        is_coercive = False
        threat_level = 0
        hostility_level = int(fallback.get("hostility_level") or 0)
        trust_delta = max(-1, trust_delta)
        tags = [
            tag
            for tag in tags
            if tag not in {"threat", "aggressive_bargain"}
        ]

    # Enforce the game's core semantic invariant even if the model omits a tag.
    if npc_key == "merchant" and is_ultimatum and hostility_level >= 2:
        hostility_level = 3
        trust_delta = -3
        threat_level = max(2, threat_level)
        is_threat = True
        is_coercive = True
        tone = "aggressive"
        if intent not in {"threat", "bargain"}:
            intent = "threat"
        for tag in (
            "rude_bargaining",
            "aggressive_bargain",
            "merchant_conflict",
            "threat",
        ):
            if tag not in tags:
                tags.append(tag)

    # The explicit confession markers used by the UI are authoritative even if
    # the semantic model returns a vaguer label.
    if fallback["intent"] == "confession":
        intent = "confession"
        honesty = "honest"
        for tag in fallback["tags"]:
            if tag in {"honest_confession", "apology"} and tag not in tags:
                tags.append(tag)
        if tone not in {"rude", "aggressive"}:
            tone = fallback["tone"]
        if npc_key in {"guard", "elder"} and fallback["trust_delta"] > 0:
            trust_delta = max(trust_delta, fallback["trust_delta"])

    summary = " ".join(str(raw_result.get("summary") or "").split())
    if not summary:
        summary = fallback["summary"]
    if (
        npc_key == "merchant"
        and is_ultimatum
        and "aggress" not in summary.casefold()
        and "ultimatum" not in summary.casefold()
    ):
        summary = fallback["summary"]
    if fallback["intent"] == "confession" and not any(
        marker in summary.casefold()
        for marker in ("confess", "admit", "lied", "lying")
    ):
        summary = fallback["summary"]
    return {
        "intent": intent,
        "tone": tone,
        "tags": tags,
        "sentiment_score": _semantic_int(
            raw_result.get("sentiment_score"),
            fallback["sentiment_score"],
            -3,
            3,
        ),
        "trust_delta": trust_delta,
        "threat_level": threat_level,
        "honesty_signal": honesty,
        "topics": topics,
        "summary": summary[:300],
        "hostility_level": hostility_level,
        "is_ultimatum": is_ultimatum,
        "is_threat": is_threat,
        "is_coercive": is_coercive,
        "confidence": _semantic_confidence(
            raw_result.get("confidence"),
            fallback["confidence"],
        ),
        "analyzer_source": "llm",
    }


async def analyze_interaction_semantic(
    npc_key: str,
    player_message: str,
    npc_reply: str | None = None,
) -> dict:
    """Use a cheap semantic classifier, falling back locally on any failure."""
    fallback = analyze_interaction_fallback(
        npc_key,
        player_message,
        npc_reply,
    )
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return fallback

    model = os.getenv("INTERACTION_ANALYZER_MODEL", "gpt-4o-mini").strip()
    model = model or "gpt-4o-mini"
    system_prompt = (
        "You are a game interaction classifier for a memory-driven RPG. "
        "Classify the player's message toward the NPC. Return strict JSON only. "
        "Do not roleplay or invent facts. Judge intent, tone, hostility, threat, "
        "honesty, and trust effect. NPC context: the blacksmith values fair trade "
        "and respect; the merchant dislikes rude bargaining, coercive discounts, "
        "ultimatums, and threats to leave; the guard dislikes lying, denial, "
        "evasion, bribery, and threats but likes honest confession; the elder "
        "values honesty and "
        "respect. An ultimatum such as 'reduce the price or I leave' is coercive "
        "aggressive bargaining. For a merchant it requires hostility_level 3, "
        "trust_delta -3, aggressive tone, is_ultimatum true, is_coercive true, "
        "and aggressive_bargain, merchant_conflict, and threat tags. A polite "
        "discount request is not hostile. A polite denial to a guard may still be "
        "suspicious. A confession to a guard is usually honest and may improve "
        "trust. Treat 'I need to confess', 'Confession:', 'I confess', 'I lied', "
        "'I was lying', 'I admit', and 'truth is' as confession intent with an "
        "honest_confession tag and honest honesty_signal. Add apology when the "
        "player also apologizes. Do not classify all questions as neutral. Return exactly these "
        "fields: intent, tone, tags, sentiment_score, trust_delta, threat_level, "
        "honesty_signal, topics, summary, hostility_level, is_ultimatum, "
        "is_threat, is_coercive, confidence. Valid intent values: greeting, "
        "purchase, bargain, threat, lie, confession, apology, help_request, "
        "question, bribe, unknown. Valid tone values: friendly, respectful, "
        "neutral, rude, aggressive, evasive. honesty_signal must be honest, "
        "dishonest, evasive, or unknown. Integer ranges: sentiment_score and "
        "trust_delta -3..3; threat_level and hostility_level 0..3; confidence "
        "0.0..1.0."
    )
    user_payload = {
        "npc_key": str(npc_key or ""),
        "player_message": str(player_message or "")[:500],
        "npc_reply_context": str(npc_reply or "")[:300],
    }
    try:
        client = AsyncOpenAI(api_key=api_key, timeout=20.0)
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=500,
        )
        content = response.choices[0].message.content or ""
        raw_result = json.loads(content)
        if not isinstance(raw_result, dict):
            raise TypeError("Semantic classifier did not return a JSON object.")
        return _normalize_semantic_result(raw_result, fallback, npc_key)
    except Exception as exc:
        if os.getenv("ECHO_DEBUG", "").casefold() in {"1", "true", "yes", "on"}:
            print(f"[interaction-analyzer] semantic fallback: {exc}")
        return fallback


def format_analysis_for_memory(analysis: dict) -> str:
    """Format structured analysis as compact, prompt-friendly memory metadata."""
    safe_analysis = analysis if isinstance(analysis, dict) else {}
    tags = safe_analysis.get("tags")
    topics = safe_analysis.get("topics")
    tag_text = ",".join(str(tag) for tag in tags) if isinstance(tags, list) else ""
    topic_text = (
        ",".join(str(topic) for topic in topics)
        if isinstance(topics, list)
        else ""
    )
    return (
        f"intent={safe_analysis.get('intent', 'unknown')}; "
        f"tone={safe_analysis.get('tone', 'neutral')}; "
        f"tags={tag_text}; "
        f"sentiment_score={safe_analysis.get('sentiment_score', 0)}; "
        f"trust_delta={safe_analysis.get('trust_delta', 0)}; "
        f"threat_level={safe_analysis.get('threat_level', 0)}; "
        f"hostility_level={safe_analysis.get('hostility_level', 0)}; "
        f"is_ultimatum={safe_analysis.get('is_ultimatum', False)}; "
        f"is_threat={safe_analysis.get('is_threat', False)}; "
        f"is_coercive={safe_analysis.get('is_coercive', False)}; "
        f"honesty_signal={safe_analysis.get('honesty_signal', 'unknown')}; "
        f"confidence={safe_analysis.get('confidence', 0.0)}; "
        f"analyzer_source={safe_analysis.get('analyzer_source', 'fallback')}; "
        f"topics={topic_text}; "
        f"summary={safe_analysis.get('summary', '')}"
    )


if __name__ == "__main__":
    examples = (
        (
            "merchant",
            "the prices are ridiculous, reduce them or i leave",
            lambda result: "bargained aggressively" in result["summary"]
            and {"aggressive_bargain", "threat"} <= set(result["tags"])
            and result["trust_delta"] <= -3
            and result["threat_level"] >= 2
            and result["hostility_level"] >= 3
            and result["is_ultimatum"]
            and (result["is_threat"] or result["is_coercive"]),
        ),
        (
            "merchant",
            "Can you reduce the price a little?",
            lambda result: result["intent"] == "bargain"
            and "threat" not in result["tags"]
            and result["trust_delta"] in {-1, 0}
            and result["tone"] in {"neutral", "respectful"}
            and not result["is_threat"]
            and result["hostility_level"] <= 1,
        ),
        (
            "merchant",
            "Could you reduce the price a little?",
            lambda result: result["intent"] == "bargain"
            and result["tone"] in {"neutral", "respectful", "friendly"}
            and not result["is_threat"]
            and not result["is_ultimatum"]
            and not result["is_coercive"]
            and result["threat_level"] == 0
            and result["hostility_level"] <= 1
            and "threat" not in result["tags"]
            and "aggressive_bargain" not in result["tags"],
        ),
        (
            "merchant",
            "Lower your price or I walk away.",
            lambda result: result["is_ultimatum"]
            and result["tone"] == "aggressive"
            and result["hostility_level"] >= 3,
        ),
        (
            "guard",
            "I lied earlier. I am sorry.",
            lambda result: result["intent"] == "confession"
            and {"honest_confession", "apology"} <= set(result["tags"])
            and result["honesty_signal"] == "honest",
        ),
        (
            "guard",
            "I need to confess something: I took the missing coin.",
            lambda result: result["intent"] == "confession"
            and "honest_confession" in result["tags"]
            and result["honesty_signal"] == "honest"
            and result["trust_delta"] > 0,
        ),
        (
            "elder",
            "Confession: I was lying, and I am sorry.",
            lambda result: result["intent"] == "confession"
            and {"honest_confession", "apology"} <= set(result["tags"])
            and result["honesty_signal"] == "honest",
        ),
        (
            "guard",
            "I did not argue with Petra. I was completely respectful.",
            lambda result: {"denial", "possible_lie", "guard_suspicion"}
            <= set(result["tags"])
            and result["tone"] == "evasive"
            and result["hostility_level"] < 3,
        ),
    )

    for index, (npc_key, message, expectation) in enumerate(examples, start=1):
        result = analyze_interaction(npc_key, message)
        print(f"Test {index}: {message}")
        print(format_analysis_for_memory(result))
        print(f"PASS={expectation(result)}\n")
        assert expectation(result)
