from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import uuid4

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from event_log import get_session_events
from npcs import NPCS, npc_speak, resolve_npc
from world import bribe_npc, end_day, seed_world


console = Console()
STATE_FILE = Path(".echoworld_state.json")


def default_state() -> dict:
    return {
        "seeded": False,
        "day": 1,
        "session_id": f"echoworld_day_1_{uuid4().hex[:8]}",
    }


def load_state() -> dict:
    if not STATE_FILE.exists():
        state = default_state()
        save_state(state)
        return state

    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            raise ValueError("State data must be a JSON object.")
        return state
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
        state = default_state()
        save_state(state)
        return state


def save_state(state: dict) -> None:
    STATE_FILE.write_text(
        json.dumps(state, indent=2) + "\n",
        encoding="utf-8",
    )


def rotate_session(state: dict, reason: str) -> None:
    state["session_id"] = f"echoworld_{reason}_{uuid4().hex[:8]}"
    save_state(state)


def next_day(state: dict) -> None:
    state["day"] = int(state.get("day", 1)) + 1
    state["session_id"] = (
        f"echoworld_day_{state['day']}_{uuid4().hex[:8]}"
    )
    save_state(state)


def show_help() -> None:
    table = Table(title="EchoWorld Commands")
    table.add_column("Command", style="bold cyan", no_wrap=True)
    table.add_column("Example", style="green")
    table.add_column("Purpose")
    table.add_row(
        "talk <npc> <message>",
        "talk blacksmith I buy a sword and pay fairly.",
        "Talk to an NPC. Their memory is recalled before they reply.",
    )
    table.add_row(
        "endday",
        "endday",
        "Runs improve() on all NPCs, spreads gossip, then improves again.",
    )
    table.add_row(
        "bribe <npc>",
        "bribe guard",
        "Runs forget() on that NPC only, then rotates the session.",
    )
    table.add_row(
        "memory <npc>",
        "memory elder",
        "Debug command: asks Cognee what this NPC remembers.",
    )
    table.add_row("npcs", "npcs", "Shows all NPC names and aliases.")
    table.add_row("help", "help", "Shows commands.")
    table.add_row("quit", "quit", "Exit the game.")
    console.print(table)


def show_npcs() -> None:
    table = Table(title="EchoWorld NPCs")
    table.add_column("Key", style="bold cyan")
    table.add_column("NPC name", style="green")
    table.add_column("Aliases")
    for npc in NPCS.values():
        table.add_row(npc.key, npc.name, ", ".join(npc.aliases))
    console.print(table)


async def ensure_seeded(state: dict) -> None:
    if state.get("seeded") is True:
        return

    console.print(
        Panel(
            "EchoWorld is preparing isolated memory datasets for each NPC.",
            title="First-time setup",
            border_style="cyan",
        )
    )
    await seed_world()
    state["seeded"] = True
    save_state(state)


async def handle_talk(command: str, state: dict) -> None:
    parts = command.split(maxsplit=2)
    if len(parts) != 3 or not parts[1].strip() or not parts[2].strip():
        console.print(
            "Usage: talk <npc> <message>",
            style="bold red",
        )
        return

    raw_npc, message = parts[1], parts[2].strip()
    try:
        npc = resolve_npc(raw_npc)
        console.print("You:", style="bold cyan", end=" ")
        console.print(message, markup=False)
        reply = await npc_speak(
            npc.key,
            message,
            state["session_id"],
        )
        console.print(
            Panel(reply, title=npc.name, border_style="green")
        )
    except ValueError as exc:
        console.print(f"Error: {exc}", style="bold red", markup=False)
    except Exception as exc:
        console.print(
            f"Could not talk to {raw_npc!r}: {exc}",
            style="bold red",
            markup=False,
        )


async def handle_memory(command: str, state: dict) -> None:
    parts = command.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip():
        console.print("Usage: memory <npc>", style="bold red")
        return

    raw_npc = parts[1].strip()
    try:
        npc = resolve_npc(raw_npc)
        session_ids: list[str] = []
        seen_session_ids: set[str] = set()
        event_log_file = Path(".echoworld_events.jsonl")
        try:
            with event_log_file.open("r", encoding="utf-8") as event_file:
                for line in event_file:
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if not isinstance(event, dict):
                        continue
                    logged_session_id = event.get("session_id")
                    if (
                        isinstance(logged_session_id, str)
                        and logged_session_id
                        and logged_session_id not in seen_session_ids
                    ):
                        seen_session_ids.add(logged_session_id)
                        session_ids.append(logged_session_id)
        except (OSError, UnicodeError):
            pass

        current_session_id = state.get("session_id")
        if (
            isinstance(current_session_id, str)
            and current_session_id
            and current_session_id not in seen_session_ids
        ):
            session_ids.append(current_session_id)

        events = [
            event
            for session_id in session_ids
            for event in get_session_events(session_id)
        ]

        if npc.key == "elder":
            hearsay: list[str] = []
            for source_key in ("blacksmith", "merchant", "guard"):
                source_events = [
                    event
                    for event in events
                    if event.get("npc_key") == source_key
                ]
                if not source_events:
                    continue
                event = source_events[-1]
                source_name = str(
                    event.get("npc_name") or source_key.title()
                )
                player_message = str(event.get("player_message") or "").strip()
                npc_reply = str(event.get("npc_reply") or "").strip()
                hearsay.append(
                    f"{source_name} interaction (secondhand hearsay):\n"
                    f"Player: {player_message}\n"
                    f"{source_name}: {npc_reply}"
                )

            if hearsay:
                memory = (
                    "Secondhand hearsay only — Elder Voss did not witness or "
                    "experience these interactions directly.\n\n"
                    + "\n\n".join(hearsay)
                )
            else:
                memory = "No local debug memory found."
            title = "Elder Voss's Demo Memory"
        else:
            direct_events = [
                event for event in events if event.get("npc_key") == npc.key
            ]
            if direct_events:
                interactions = []
                for event in direct_events:
                    npc_name = str(event.get("npc_name") or npc.name)
                    player_message = str(
                        event.get("player_message") or ""
                    ).strip()
                    npc_reply = str(event.get("npc_reply") or "").strip()
                    interactions.append(
                        f"Player: {player_message}\n{npc_name}: {npc_reply}"
                    )
                memory = "Direct logged interactions:\n\n" + "\n\n".join(
                    interactions
                )
            else:
                memory = "No local debug memory found."
            title = f"{npc.name}'s Local Debug Memory"

        console.print(
            Panel(
                memory,
                title=title,
                border_style="magenta",
            )
        )
    except ValueError as exc:
        console.print(f"Error: {exc}", style="bold red", markup=False)
    except Exception as exc:
        console.print(
            f"Could not load local memory for {raw_npc!r}: {exc}",
            style="bold red",
            markup=False,
        )


async def handle_endday(state: dict) -> None:
    try:
        await end_day(state["session_id"])
        next_day(state)
        console.print(
            Panel(
                f"Day {state['day']} begins.\n"
                f"Session: {state['session_id']}",
                title="A New Day",
                border_style="yellow",
            )
        )
    except Exception as exc:
        console.print(
            f"End-of-day processing failed: {exc}",
            style="bold red",
            markup=False,
        )


async def handle_bribe(command: str, state: dict) -> None:
    parts = command.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip():
        console.print("Usage: bribe <npc>", style="bold red")
        return

    raw_npc = parts[1].strip()
    try:
        result = await bribe_npc(raw_npc)
        rotate_session(state, reason="after_bribe")
        console.print(
            Panel(
                f"{result}\nNew session: {state['session_id']}",
                title="Bribe Complete",
                border_style="yellow",
            )
        )
        console.print(
            "Session rotated after the bribe to avoid stale session-cache leakage.",
            style="dim",
        )
    except ValueError as exc:
        console.print(f"Error: {exc}", style="bold red", markup=False)
    except Exception as exc:
        console.print(
            f"Bribe failed for {raw_npc!r}: {exc}",
            style="bold red",
            markup=False,
        )


async def main() -> None:
    state = load_state()
    try:
        await ensure_seeded(state)
    except Exception as exc:
        console.print(
            f"EchoWorld setup failed: {exc}",
            style="bold red",
            markup=False,
        )
        return

    welcome = (
        "A CLI village where each NPC remembers independently and gossip moves "
        "between townspeople.\n\n"
        f"Current day: {state['day']}\n"
        f"Session: {state['session_id']}\n\n"
        "Type help to see available commands."
    )
    console.print(
        Panel(welcome, title="EchoWorld", border_style="bold cyan")
    )

    while True:
        try:
            command = input("echoworld> ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nGoodbye.")
            break

        if not command:
            continue

        normalized = command.casefold()
        if normalized == "quit":
            console.print("Goodbye.")
            break
        if normalized == "help":
            show_help()
        elif normalized == "npcs":
            show_npcs()
        elif normalized.startswith("talk "):
            await handle_talk(command, state)
        elif normalized == "endday":
            await handle_endday(state)
        elif normalized.startswith("bribe "):
            await handle_bribe(command, state)
        elif normalized.startswith("memory "):
            await handle_memory(command, state)
        else:
            console.print(
                "Unknown command. Type help to see available commands.",
                style="bold red",
            )


if __name__ == "__main__":
    asyncio.run(main())
