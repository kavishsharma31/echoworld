from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dataset_registry import get_dataset_name
from dotenv import load_dotenv
from event_log import append_event, build_elder_hearsay_from_events
from interaction_analyzer import analyze_interaction_semantic


load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

_openai_api_key = os.getenv("OPENAI_API_KEY")
if not os.getenv("LLM_API_KEY") and _openai_api_key:
    os.environ["LLM_API_KEY"] = _openai_api_key
if not os.getenv("EMBEDDING_API_KEY") and _openai_api_key:
    os.environ["EMBEDDING_API_KEY"] = _openai_api_key

# Cognee reads its provider configuration during import, so import it only after
# the environment variables above have been prepared.
import cognee
from cognee_bootstrap import ensure_cognee_connected
from openai import AsyncOpenAI


NPC_MODEL = os.getenv("NPC_MODEL", "gpt-4o") or "gpt-4o"
DEBUG = os.getenv("ECHO_DEBUG", "false").strip().casefold() in {
    "1",
    "true",
    "yes",
    "on",
}


@dataclass(frozen=True)
class NPC:
    key: str
    name: str
    role: str
    personality: str
    dataset: str
    aliases: tuple[str, ...]


NPCS: dict[str, NPC] = {
    "blacksmith": NPC(
        key="blacksmith",
        name="Gareth the Blacksmith",
        role="Village blacksmith",
        personality=(
            "Gruff but fair. Respects honest customers and remembers reliable buyers."
        ),
        dataset="npc_gareth_blacksmith",
        aliases=("blacksmith", "gareth", "smith"),
    ),
    "guard": NPC(
        key="guard",
        name="Captain Mira the Guard",
        role="Captain of the village guard",
        personality=(
            "Strict, observant, suspicious of contradictions. Values order and truth."
        ),
        dataset="npc_mira_guard",
        aliases=("guard", "mira", "captain", "captain mira"),
    ),
    "merchant": NPC(
        key="merchant",
        name="Petra the Merchant",
        role="Village merchant",
        personality=(
            "Sharp, transactional, proud. Never forgets a bad deal or a rude customer."
        ),
        dataset="npc_petra_merchant",
        aliases=("merchant", "petra", "shopkeeper"),
    ),
    "elder": NPC(
        key="elder",
        name="Elder Voss",
        role="Village elder",
        personality=(
            "Wise, restrained, politically careful. Hears everything eventually."
        ),
        dataset="npc_elder_voss",
        aliases=("elder", "voss", "elder voss"),
    ),
}


def get_active_dataset(npc_key: str) -> str:
    npc = NPCS[npc_key]
    return get_dataset_name(npc_key, npc.dataset)


ALIAS_TO_KEY: dict[str, str] = {
    alias.casefold(): npc.key for npc in NPCS.values() for alias in npc.aliases
}


def resolve_npc(raw: str) -> NPC:
    normalized = " ".join(raw.strip().casefold().split())
    key = ALIAS_TO_KEY.get(normalized)
    if key is None:
        valid_aliases = ", ".join(sorted(ALIAS_TO_KEY))
        raise ValueError(
            f"Unknown NPC {raw!r}. Valid aliases are: {valid_aliases}."
        )
    return NPCS[key]


def clean_recall_text(text: str) -> str:
    if not text:
        return ""

    cleaned = text.replace("__node_content_start__", " ")
    cleaned = cleaned.replace("__node_content_end__", " ")
    for fragment in (
        "kind='graph_completion'",
        'kind="graph_completion"',
        "search_type='GRAPH_COMPLETION'",
        'search_type="GRAPH_COMPLETION"',
        "metadata=",
        "raw=",
    ):
        if fragment in cleaned:
            cleaned = cleaned.split(fragment, maxsplit=1)[0]
    if "Nodes:" in cleaned:
        cleaned = cleaned.split("Nodes:", maxsplit=1)[0]
    if "Connections:" in cleaned:
        cleaned = cleaned.split("Connections:", maxsplit=1)[0]
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(
        r"(?:^|\s)(?:session|graph|vector|node|nodes|connection|connections)$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    return cleaned


def _recall_item_to_text(item: Any, seen: set[int]) -> str:
    if item is None:
        return ""
    if isinstance(item, str):
        return clean_recall_text(item)

    item_id = id(item)
    if item_id in seen:
        return ""

    if isinstance(item, (Mapping, list, tuple)) or hasattr(item, "__dict__"):
        seen.add(item_id)

    if isinstance(item, Mapping):
        parts: list[str] = []
        structured_value_found = False
        for key in (
            "text",
            "answer",
            "context",
            "content",
            "raw",
            "question",
            "source",
        ):
            if key not in item or item[key] is None:
                continue
            structured_value_found = True
            block = clean_recall_text(_recall_item_to_text(item[key], seen))
            if block:
                parts.append(block)
        if parts:
            return clean_recall_text(" ".join(parts))
        if structured_value_found:
            return ""
        return clean_recall_text(str(item))

    if isinstance(item, (list, tuple)):
        parts: list[str] = []
        for value in item:
            block = clean_recall_text(_recall_item_to_text(value, seen))
            if block:
                parts.append(block)
        return clean_recall_text(" ".join(parts))

    try:
        text_value = getattr(item, "text", None)
    except Exception:
        text_value = None
    structured_value_found = text_value is not None
    if text_value is not None:
        text = clean_recall_text(_recall_item_to_text(text_value, seen))
        if text:
            return text

    parts: list[str] = []
    for attribute in ("answer", "context", "question", "source"):
        try:
            value = getattr(item, attribute, None)
        except Exception:
            continue
        if value is not None:
            structured_value_found = True
            text = clean_recall_text(_recall_item_to_text(value, seen))
            if text:
                parts.append(text)
    if parts:
        return clean_recall_text(" ".join(parts))
    if structured_value_found:
        return ""

    return clean_recall_text(str(item))


def recall_results_to_text(results: Any, max_chars: int = 5000) -> str:
    if results is None or max_chars <= 0:
        return ""

    items = results if isinstance(results, (list, tuple)) else [results]
    seen: set[int] = set()
    parts: list[str] = []
    for item in items:
        block = clean_recall_text(_recall_item_to_text(item, seen))
        if block:
            parts.append(block)
    joined = clean_recall_text("\n".join(parts))
    return joined[:max_chars].rstrip()


async def _cognee_remember(
    text: str,
    dataset_name: str,
    session_id: str | None = None,
    self_improvement: bool = False,
) -> Any:
    await ensure_cognee_connected()
    try:
        return await cognee.remember(
            text,
            dataset_name=dataset_name,
            session_id=session_id,
            self_improvement=self_improvement,
        )
    except TypeError:
        return await cognee.remember(
            text,
            dataset=dataset_name,
            session_id=session_id,
            self_improvement=self_improvement,
        )


async def _cognee_recall(
    query: str,
    dataset_name: str,
    session_id: str | None = None,
    only_context: bool = True,
) -> str:
    def dataset_is_missing(exc: Exception) -> bool:
        error_name = type(exc).__name__.casefold()
        error_message = str(exc).casefold()
        return (
            "datasetnotfound" in error_name
            or "no datasets found" in error_message
            or "dataset not found" in error_message
            or "dataset does not exist" in error_message
        )

    await ensure_cognee_connected()

    # session_id remains in the signature for compatibility. Recall is always
    # permanent-dataset-only to avoid triggering session cognification.
    try:
        permanent_results = await cognee.recall(
            query_text=query,
            datasets=[dataset_name],
            top_k=8,
            only_context=only_context,
        )
        return recall_results_to_text(permanent_results)
    except Exception as modern_error:
        try:
            fallback_results = await cognee.recall(
                query,
                datasets=[dataset_name],
            )
            return recall_results_to_text(fallback_results)
        except Exception as fallback_error:
            if (
                dataset_is_missing(modern_error)
                or dataset_is_missing(fallback_error)
            ):
                return ""
            raise


async def npc_seed(npc_key: str) -> None:
    npc = resolve_npc(npc_key)
    profile = (
        f"Character profile\n"
        f"Name: {npc.name}\n"
        f"Role: {npc.role}\n"
        f"Personality: {npc.personality}\n"
        f"Known aliases: {', '.join(npc.aliases)}"
    )
    await _cognee_remember(
        profile,
        dataset_name=get_active_dataset(npc.key),
        self_improvement=True,
    )


async def npc_remember(
    npc_key: str,
    event_text: str,
    session_id: str,
    self_improvement: bool = False,
) -> None:
    npc = resolve_npc(npc_key)
    event = event_text.strip()
    if not event:
        raise ValueError("Memory event text cannot be empty.")

    timestamp = datetime.now(timezone.utc).isoformat()
    memory = (
        f"Timestamp: {timestamp}\n"
        f"NPC: {npc.name}\n"
        f"Memory event:\n{event}"
    )
    await _cognee_remember(
        memory,
        dataset_name=get_active_dataset(npc.key),
        session_id=session_id,
        self_improvement=self_improvement,
    )


async def npc_recall(
    npc_key: str,
    query: str,
    session_id: str | None = None,
) -> str:
    npc = resolve_npc(npc_key)
    return await _cognee_recall(
        query=query,
        dataset_name=get_active_dataset(npc.key),
        session_id=session_id,
        only_context=True,
    )


def _verified_memory_text(verified_memory: str | list[str] | None) -> str:
    if isinstance(verified_memory, list):
        return "\n".join(
            str(item).strip()
            for item in verified_memory
            if str(item).strip()
        )
    return str(verified_memory or "").strip()


def violates_memory_policy(
    reply: str,
    memory_forbidden: bool,
    verified_memory: str | list[str] | None,
    npc_key: str = "",
    current_message: str = "",
) -> bool:
    normalized_reply = reply.casefold()
    evidence = _verified_memory_text(verified_memory).casefold()
    forbidden_claims = (
        "i remember",
        "remember you",
        "you again",
        "last time",
        "as before",
        "from the market",
        "the spices",
        "you were interested",
        "when you bought",
        "when you asked",
        "welcome back",
        "back again",
        "we meet again",
        "seen you before",
    )
    has_memory_claim = any(
        phrase in normalized_reply for phrase in forbidden_claims
    )
    if has_memory_claim:
        if memory_forbidden or not evidence:
            return True
        ignored_words = {
            "again",
            "asked",
            "before",
            "bought",
            "from",
            "interested",
            "last",
            "player",
            "previously",
            "remember",
            "said",
            "time",
            "when",
            "you",
            "your",
        }
        reply_words = {
            word
            for word in re.findall(r"[a-z']+", normalized_reply)
            if len(word) >= 4 and word not in ignored_words
        }
        evidence_words = {
            word
            for word in re.findall(r"[a-z']+", evidence)
            if len(word) >= 4 and word not in ignored_words
        }
        if not reply_words.intersection(evidence_words):
            return True

    if npc_key == "merchant":
        allowed_item_context = f"{current_message}\n{evidence}".casefold()
        for item in ("spice", "herb", "gem", "sword", "potion"):
            if item in normalized_reply and item not in allowed_item_context:
                return True
    return False


def _safe_memory_fallback(npc_key: str, attitude: str = "neutral") -> str:
    normalized_attitude = str(attitude or "neutral").casefold().strip()
    tone_fallbacks = {
        "warm": {
            "merchant": (
                "Can't say I know you personally, but you're welcome at my "
                "stall. Petra's my name. What can I find for you?"
            ),
            "blacksmith": (
                "New face at the forge, eh? Gareth. Tell me what steel you need "
                "and I'll see what I can do."
            ),
            "guard": (
                "I do not recall meeting you, but you're welcome in EchoWorld. "
                "Captain Mira. How may I help?"
            ),
            "elder": (
                "I do not yet know your story, but you are welcome to share it. "
                "Village stories reach me after nightfall."
            ),
        },
        "suspicious": {
            "merchant": "I don't know you. Petra's my name. State your business.",
            "blacksmith": "I don't know you. Gareth. Say plainly what you need.",
            "guard": "I do not recall you. State your business carefully.",
            "elder": "I do not know your story yet. Choose your words carefully.",
        },
        "hostile": {
            "merchant": "I don't know you. Buy something or move along.",
            "blacksmith": "I don't know you. Make your business at the forge brief.",
            "guard": "I do not recall you. State your business and be quick.",
            "elder": "I do not know your story. I have little patience for games.",
        },
    }
    if normalized_attitude in tone_fallbacks:
        return tone_fallbacks[normalized_attitude].get(
            npc_key,
            "I do not know you. State your business.",
        )

    fallbacks = {
        "merchant": (
            "Can't say I know you personally. Petra's my name, and this stall "
            "runs on fair coin and sharper eyes. What are you looking for?"
        ),
        "blacksmith": (
            "New face at the forge, eh? Gareth. If you need steel, speak plainly."
        ),
        "guard": "I do not recall you. State your business.",
        "elder": (
            "I do not yet know your story. Stories reach me after the village "
            "has had time to speak."
        ),
    }
    return fallbacks.get(
        npc_key,
        "I do not have a clear memory of you. Tell me what brings you here.",
    )


async def npc_speak(
    npc_key: str,
    player_message: str,
    session_id: str,
    allow_hearsay: bool = True,
    is_first_meeting: bool = False,
    verified_memory: str | list[str] | None = None,
    memory_forbidden: bool = False,
    hearsay_session_id: str | None = None,
    attitude: str = "neutral",
    return_trace: bool = False,
    promise_context: str = "",
    forced_callout: str = "",
) -> str | dict:
    npc = resolve_npc(npc_key)
    message = player_message.strip()
    if not message:
        raise ValueError("Player message cannot be empty.")

    elder_before_gossip = npc.key == "elder" and not allow_hearsay
    legacy_memory_mode = verified_memory is None
    verified_text = _verified_memory_text(verified_memory)
    verified_promise_context = " ".join(str(promise_context or "").split())
    verified_forced_callout = " ".join(str(forced_callout or "").split())
    if npc.key != "guard":
        verified_forced_callout = ""
    hearsay_text = ""
    recalled_memory = ""
    if npc.key == "elder" and allow_hearsay:
        hearsay_text = build_elder_hearsay_from_events(
            session_id=hearsay_session_id,
        )

    evidence_parts = []
    if verified_text:
        evidence_parts.append(verified_text)
    if verified_promise_context:
        evidence_parts.append(
            "Verified promise state:\n" + verified_promise_context
        )
    if hearsay_text:
        evidence_parts.append(
            "Verified secondhand village hearsay:\n" + hearsay_text
        )
    if (
        not is_first_meeting
        and not memory_forbidden
        and not elder_before_gossip
    ):
        recalled_memory = await npc_recall(
            npc.key,
            message,
            session_id=session_id,
        )
        if legacy_memory_mode and recalled_memory:
            evidence_parts.insert(0, recalled_memory)

    # Strict callers expose only verified local evidence. Recall may still run
    # for established relationships, but stale output cannot become prompt facts.
    policy_evidence = "\n\n".join(evidence_parts)
    memory_context = policy_evidence or "No verified memory evidence."

    pre_gossip_instruction = ""
    if elder_before_gossip:
        if is_first_meeting:
            pre_gossip_instruction = (
                " The player is a new face. You have not heard personal stories "
                "about them from the village yet. Do not claim to know their "
                "actions with Gareth, Petra, or Mira. You may explain that "
                "stories reach you after nightfall."
            )
        else:
            pre_gossip_instruction = (
                " You have met the player directly in this current run, so you "
                "may acknowledge that meeting. However, no personal stories from "
                "Gareth, Petra, or Mira have reached you yet. Do not claim "
                "to know the player's actions with them. You may explain that "
                "village stories settle after nightfall."
            )

    first_meeting_instruction = ""
    if is_first_meeting:
        first_meeting_instruction = (
            " This is your first direct meeting with the player in the current "
            "run. Do not claim to know them. Do not say 'again', 'I remember "
            "you', 'last time', 'as before', or refer to earlier personal "
            "interactions. Introduce yourself naturally and respond to their "
            "current message. You may know your own role, workplace, village, "
            "and responsibilities, but not the player personally."
        )

    returning_meeting_instruction = ""
    if not is_first_meeting and not memory_forbidden and policy_evidence:
        returning_meeting_instruction = (
            " This is not your first direct meeting with the player in the "
            "current run. Maintain that familiarity across day and session "
            "changes. Do not introduce yourself as though they are a stranger. "
            "Use concrete remembered details when the memory context provides "
            "them; if it is sparse, acknowledge familiarity without inventing "
            "specific past events."
        )

    memory_policy_instruction = (
        "\nVERIFIED MEMORY POLICY:\n"
        "You may only claim to remember the player if VERIFIED MEMORY contains "
        "a relevant fact. If VERIFIED MEMORY is empty, do not say 'I remember', "
        "'you again', 'last time', 'as before', or mention specific past "
        "interactions. Do not invent shop items, purchases, arguments, discounts, "
        "market visits, or prior meetings. If the player asks whether you remember "
        "them and VERIFIED MEMORY is empty, say you do not have a clear memory of "
        "them. If memory is forbidden for this response, treat the player as "
        "unknown for direct personal memory. Elder Voss may still relay verified "
        "hearsay when it is explicitly present."
    )
    if npc.key == "merchant":
        memory_policy_instruction += (
            " Petra may discuss goods, prices, bargains, and her stall generally, "
            "but must not mention specific items such as spices, herbs, gems, "
            "swords, or potions unless the current player message or VERIFIED "
            "MEMORY contains that item."
        )
    if memory_forbidden:
        memory_policy_instruction += (
            " MEMORY IS FORBIDDEN for this response: treat the player as unknown."
        )
    structured_memory_instruction = (
        "\nSTRUCTURED MEMORY EVIDENCE POLICY:\n"
        "Structured summaries in the evidence are verified facts from the "
        "player's current-run interactions. You may use them for continuity and "
        "tone, but must not invent details beyond those summaries. Structured "
        "memory controls facts; attitude controls delivery only."
    )
    verified_memory_section = policy_evidence or "[empty]"

    normalized_attitude = str(attitude or "neutral").casefold().strip()
    if normalized_attitude not in {"warm", "neutral", "suspicious", "hostile"}:
        normalized_attitude = "neutral"
    tone_guidance = {
        "warm": (
            "Speak more openly and helpfully. You may sound pleased to see the "
            "player only when verified memory supports recognizing them."
        ),
        "neutral": "Use your normal in-character tone.",
        "suspicious": (
            "Be guarded and doubtful, and question the player's honesty. Do not "
            "sound angry unless verified evidence shows direct hostility. Do not "
            "invent accusations or supposed past misconduct."
        ),
        "hostile": (
            "Be angry, curt, sharp, confrontational, and unwilling to offer "
            "favors. Do not become violent unless the player escalates. Never "
            "invent specific past offenses, and refer to past insults or threats "
            "only when verified memory supports them."
        ),
    }[normalized_attitude]
    attitude_instruction = (
        "\nATTITUDE / TONE POLICY:\n"
        f"Current attitude: {normalized_attitude}. {tone_guidance} "
        "Attitude affects delivery only; it never creates facts or personal "
        "memory. Mention past events only when VERIFIED MEMORY supports them. "
        "If memory is forbidden, keep this tone while treating the player as "
        "unknown. For example, suspicion may say 'I am not in the mood for "
        "games,' but must not invent a claim such as 'Last time you stole from "
        "me.'"
    )
    confession_instruction = (
        "\nCONFESSION RESPONSE POLICY:\n"
        "If the player's current message is a confession, respond seriously to "
        "only what they explicitly confessed. Do not invent additional crimes, "
        "victims, motives, or details. A guard may become more attentive while "
        "still respecting honesty. A hostile attitude may soften slightly in "
        "delivery, but only verified memory and the current confession establish "
        "facts."
    )
    promise_instruction = ""
    if verified_promise_context:
        promise_instruction = (
            "\nPROMISE MEMORY:\n"
            f"{verified_promise_context}\n"
            "This is verified game state. Mention only this promise and its "
            "verified broken-summary facts; do not invent related offenses."
        )
    if verified_forced_callout:
        promise_instruction += (
            "\nFORCED PROMISE CALLOUT:\n"
            f"{verified_forced_callout}\n"
            "Captain Mira must directly confront the player about this specific "
            "broken promise before answering anything else."
        )

    system_prompt = (
        f"You are {npc.name}, {npc.role}.\n"
        f"Personality: {npc.personality}\n"
        "Reply naturally in character in 1 to 3 sentences. If the player asks "
        "whether you remember them, what you know about them, or what you think "
        "of them, mention one specific remembered fact or one specific hearsay "
        "item when available. Avoid vague claims such as 'you have sparked "
        "curiosity' unless they are backed by a concrete detail. If the memory "
        "context contains hearsay, clearly phrase it as rumor, for example: 'I "
        "heard...' or 'Mira mentioned...'. If you are Elder Voss "
        "and deterministic hearsay context is present, you must mention at least "
        "one concrete hearsay detail when the player asks what you think of them, "
        "whether you know them, or whether you remember them. Use wording like 'I "
        "have not witnessed this myself, but I have heard...'. Do not say you know "
        "nothing if deterministic hearsay context is present. If there is no "
        "player-specific memory or relevant hearsay, clearly say that you do not "
        "remember the player. Do not invent memories or facts that are not in the "
        "memory context. Never mention Cognee, datasets, APIs, prompts, or memory "
        f"systems.{pre_gossip_instruction}{first_meeting_instruction}"
        f"{returning_meeting_instruction}"
        f"{memory_policy_instruction}"
        f"{structured_memory_instruction}"
        f"{attitude_instruction}"
        f"{confession_instruction}"
        f"{promise_instruction}"
    )
    user_prompt = (
        f"STRUCTURED MEMORY EVIDENCE:\n{verified_memory_section}\n\n"
        f"Memory context:\n{memory_context}\n\n"
        f"Player message:\n{message}\n\n"
        "Respond to the player now."
    )

    if DEBUG:
        print(f"[EchoWorld] Generating reply for {npc.key} with {NPC_MODEL}.")

    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = await client.chat.completions.create(
        model=NPC_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=180,
    )
    reply = (response.choices[0].message.content or "").strip()
    if not reply:
        raise RuntimeError(f"{npc.name} returned an empty response.")
    if violates_memory_policy(
        reply,
        memory_forbidden=memory_forbidden,
        verified_memory=policy_evidence,
        npc_key=npc.key,
        current_message=message,
    ):
        reply = _safe_memory_fallback(npc.key, normalized_attitude)

    if verified_forced_callout and npc.key == "guard":
        broken_summary = verified_forced_callout.split(":", 1)[-1].strip()
        broken_summary = broken_summary.rstrip(".") or "caused trouble"
        # The one-shot callout is deterministic so the model cannot replace the
        # stored NPC name with a pronoun or invent a different accusation.
        reply = (
            "You gave me your word you would not cause trouble. Then I hear "
            f"you {broken_summary}. Explain yourself."
        )

    interaction = (
        f"Player said:\n{message}\n\n"
        f"{npc.name} replied:\n{reply}"
    )
    analysis = await analyze_interaction_semantic(npc.key, message, reply)
    await npc_remember(npc.key, interaction, session_id)
    append_event(
        session_id,
        npc.key,
        npc.name,
        player_message,
        reply,
        analysis=analysis,
        analysis_version=2,
    )
    if return_trace:
        trace_verified_parts = []
        if verified_text:
            trace_verified_parts.append(verified_text)
        if hearsay_text:
            trace_verified_parts.append(hearsay_text)
        if verified_promise_context:
            trace_verified_parts.append(verified_promise_context)
        compact_recall = " ".join(str(recalled_memory or "").split())[:1200]
        compact_verified = "\n".join(trace_verified_parts)[:1600]
        return {
            "reply": reply,
            "recall_trace": {
                "cognee_recall": compact_recall,
                "verified_memory": compact_verified,
                "attitude": normalized_attitude,
                "tags": list(analysis.get("tags") or []),
                "analysis_summary": str(analysis.get("summary") or ""),
                "tone": str(analysis.get("tone") or "neutral"),
                "hostility_level": int(analysis.get("hostility_level") or 0),
                "trust_delta": int(analysis.get("trust_delta") or 0),
                "analyzer_source": str(
                    analysis.get("analyzer_source") or "fallback"
                ),
                "analysis": dict(analysis),
                "memory_forbidden": bool(memory_forbidden),
                "is_first_meeting": bool(is_first_meeting),
            },
        }
    return reply
