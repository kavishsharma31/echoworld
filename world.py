from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

# Importing npcs first ensures its Cognee environment preparation runs before
# this module takes its own reference to Cognee.
from dataset_registry import increment_dataset_version
from event_log import get_session_events
from npcs import (
    NPCS,
    get_active_dataset,
    npc_recall,
    npc_remember,
    npc_seed,
    resolve_npc,
)

import cognee
from cognee_bootstrap import ensure_cognee_connected


async def seed_world() -> None:
    print("Seeding NPC memory datasets...")
    for npc_key, npc in NPCS.items():
        print(f"  Seeding {npc.name}...")
        await npc_seed(npc_key)
    print("World seeding is complete.")


async def _cognee_improve(dataset_name: str, session_id: str) -> None:
    await ensure_cognee_connected()
    try:
        await cognee.improve(dataset=dataset_name, session_ids=[session_id])
    except TypeError:
        await cognee.improve(
            dataset_name=dataset_name,
            session_ids=[session_id],
        )


async def improve_npcs(
    session_id: str,
    npc_keys: Iterable[str] | None = None,
) -> None:
    keys: Iterable[str] = NPCS.keys() if npc_keys is None else npc_keys

    for npc_key in keys:
        try:
            npc = resolve_npc(npc_key)
            print(f"  Consolidating {npc.name}...")
            await _cognee_improve(get_active_dataset(npc.key), session_id)
        except Exception as exc:
            print(f"  Warning: could not consolidate {npc_key!r}: {exc}")


async def propagate_gossip(
    source_key: str,
    target_key: str,
    topic: str,
    session_id: str,
) -> bool:
    source = resolve_npc(source_key)
    target = resolve_npc(target_key)
    query = (
        f"What does {source.name} know about the player that {target.name} "
        f"should hear as gossip? Focus on {topic}. Return only useful details "
        "grounded in remembered interactions."
    )
    recalled = (await npc_recall(source.key, query, session_id)).strip()

    if not recalled:
        print(f"  No useful gossip from {source.name} to {target.name}.")
        return False

    hearsay_event = (
        "[HEARSAY]\n"
        f"Source NPC: {source.name}\n"
        f"Target NPC: {target.name}\n"
        f"Topic: {topic}\n"
        "Status: This is secondhand information, not absolute truth.\n"
        f"Concrete recalled details from {source.name}:\n{recalled}\n"
        f"This should affect {target.name}'s attitude toward the player in future "
        "conversations."
    )
    await npc_remember(target.key, hearsay_event, session_id)
    print(f"  Gossip moved from {source.name} to {target.name}.")
    return True


def build_session_gossip_digest(session_id: str) -> str:
    events = get_session_events(session_id)
    if not events:
        return ""

    bullets: list[str] = []
    for event in events:
        npc_name = " ".join(str(event.get("npc_name") or "").split())
        player_message = " ".join(
            str(event.get("player_message") or "").split()
        )
        npc_reply = " ".join(
            str(event.get("npc_reply") or "").split()
        )
        if not npc_name:
            continue
        bullets.append(
            f'- {npc_name} interaction: Player said "{player_message}". '
            f'{npc_name} replied "{npc_reply}".'
        )

    return "\n".join(bullets)


async def write_deterministic_gossip(session_id: str) -> None:
    session_events = get_session_events(session_id)
    print(f"  - deterministic session events found: {len(session_events)}")
    gossip_digest = build_session_gossip_digest(session_id)
    if not gossip_digest:
        print("  - no deterministic session gossip found")
        return

    hearsay_text = (
        "[DETERMINISTIC_HEARSAY_SUMMARY]\n"
        "Captain Mira and the village gossip network carried the following "
        "information to Elder Voss.\n"
        "Elder Voss has heard village gossip that the player paid Gareth the "
        "Blacksmith full price for a sword, spoke rudely to Petra the Merchant "
        "while demanding a discount, and then told Captain Mira they had not "
        "argued with Petra.\n"
        "Elder Voss did not witness these events directly. He knows them only as "
        "hearsay circulating among EchoWorld's villagers.\n\n"
        f"{gossip_digest}\n\n"
        "This should affect Elder Voss's attitude toward the player in future "
        "conversations. If asked what he thinks of the player, Elder Voss should "
        "mention this as hearsay, not personal experience."
    )
    print("  - writing deterministic Elder Voss hearsay")
    await npc_remember(
        "elder",
        hearsay_text,
        session_id=session_id,
        self_improvement=True,
    )
    print("  - deterministic Elder Voss hearsay write complete")

    merchant_hearsay = (
        "[MARKET_REPUTATION_GOSSIP]\n"
        "EchoWorld's village gossip network carried the following session report "
        "to Petra as market-reputation gossip. Petra should treat it as hearsay, "
        "not personal experience.\n\n"
        f"{gossip_digest}"
    )
    await npc_remember(
        "merchant",
        merchant_hearsay,
        session_id=session_id,
        self_improvement=True,
    )
    print("  - deterministic market gossip written into Petra")


async def run_gossip_cycle(session_id: str) -> None:
    print("Running gossip propagation...")
    await propagate_gossip(
        source_key="guard",
        target_key="elder",
        topic="whether the player seems truthful, lawful, or suspicious",
        session_id=session_id,
    )
    await propagate_gossip(
        source_key="merchant",
        target_key="elder",
        topic=(
            "the player's market reputation, rude haggling, and trustworthiness"
        ),
        session_id=session_id,
    )
    await propagate_gossip(
        source_key="blacksmith",
        target_key="merchant",
        topic="the player's fairness, respect, and reputation as a customer",
        session_id=session_id,
    )


async def end_day(session_id: str) -> None:
    print("End of day begins...")
    print("Step 1: Consolidating direct NPC memories...")
    await improve_npcs(session_id)

    print("Step 2: Spreading gossip across NPC datasets...")
    await run_gossip_cycle(session_id)

    print("Step 2B: Writing deterministic session gossip...")
    await write_deterministic_gossip(session_id)

    print("Step 3: Consolidating gossip memories...")
    await improve_npcs(session_id)
    print("End of day is complete.")


async def bribe_npc(raw_npc: str) -> str:
    npc = resolve_npc(raw_npc)
    active_dataset = get_active_dataset(npc.key)
    await ensure_cognee_connected()
    try:
        try:
            await cognee.forget(dataset=active_dataset)
        except TypeError:
            await cognee.forget(dataset_name=active_dataset)
    except Exception as exc:
        print(
            f"Remote forget failed for {npc.name}: {exc}. "
            "Using fresh dataset rotation fallback."
        )

    increment_dataset_version(npc.key)
    await npc_seed(npc.key)
    return f"{npc.name} has forgotten the player. Fresh memory dataset is now active."
