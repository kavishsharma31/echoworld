"""Playable pixel-art Pygame frontend for EchoWorld's memory-driven village."""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pygame

from backend_adapter import BackendAdapter, create_backend_adapter
from tutorial_system import (
    action_completes_current_step,
    advance_tutorial_popup,
    complete_tutorial_step,
    get_current_popup_page,
    get_current_tutorial_step,
    interaction_completes_current_step,
    load_tutorial_state,
    reset_tutorial,
    skip_tutorial,
    tutorial_is_active,
)
from pixel_assets import (
    draw_dialogue_box,
    draw_menu_box,
    make_exclamation_bubble,
    make_grass_tile,
    make_npc_sprite,
    make_path_tile,
    make_player_sprite,
    make_roof_tile,
    make_tree_tile,
    make_wall_tile,
)


# Display and world constants
INTERNAL_WIDTH = 320
INTERNAL_HEIGHT = 240
SCALE = 3
WINDOW_SIZE = (INTERNAL_WIDTH * SCALE, INTERNAL_HEIGHT * SCALE)
BROWSER_PIXEL_SCALE = 3
TILE_SIZE = 16
MAP_WIDTH = 40
MAP_HEIGHT = 22
RIGHT_UI_SAFE_MARGIN_TILES = 10
FPS = 60
PLAYER_SPEED = 78.0
MAX_PLAYER_INPUT = 220
DIALOGUE_TEXT_WIDTH = 864
DIALOGUE_MAX_LINES = 3
ENDDAY_ANIMATION_MS = 7000
RECALL_NOTIFICATION_MS = 10000

MENU_OPTIONS = ("Talk", "Confess", "Bribe / Forget", "Memory", "Cancel")

ENDDAY_GATHER_TILES = {
    "blacksmith": (13.2, 9.7),
    "merchant": (14.3, 9.2),
    "guard": (15.4, 9.8),
    "elder": (14.9, 10.9),
}

ATTITUDE_COLORS = {
    "warm": (105, 210, 126),
    "neutral": (210, 214, 216),
    "suspicious": (242, 180, 72),
    "hostile": (232, 83, 76),
}
ATTITUDE_ICONS = {"warm": "+", "neutral": "=", "suspicious": "?", "hostile": "!"}
ATTITUDE_NAMES = {
    "blacksmith": "Gareth",
    "merchant": "Petra",
    "guard": "Mira",
    "elder": "Voss",
}


@dataclass(frozen=True)
class RenderMetrics:
    screen_w: int
    screen_h: int
    internal_w: int
    internal_h: int
    pixel_scale: int


@dataclass(frozen=True)
class UILayout:
    margin: int
    hud: pygame.Rect
    memory: pygame.Rect
    attitudes: pygame.Rect
    objective: pygame.Rect
    objective_with_recall: pygame.Rect
    dialogue: pygame.Rect
    recall: pygame.Rect
    menu: pygame.Rect
    tutorial: pygame.Rect
    loading: pygame.Rect


def get_display_size(browser_mode: bool) -> tuple[int, int]:
    """Read the live browser viewport, with a safe Pygbag fallback."""
    if not browser_mode:
        return WINDOW_SIZE
    try:
        import platform

        width = int(platform.window.innerWidth)
        height = int(platform.window.innerHeight)
    except Exception:
        width, height = (1280, 720)
    if width < 320 or height < 240:
        return (1280, 720)
    return (width, height)


def compute_render_metrics(
    screen_w: int,
    screen_h: int,
    browser_mode: bool,
) -> RenderMetrics:
    if not browser_mode:
        return RenderMetrics(
            WINDOW_SIZE[0],
            WINDOW_SIZE[1],
            INTERNAL_WIDTH,
            INTERNAL_HEIGHT,
            SCALE,
        )
    shortest_side = min(screen_w, screen_h)
    if screen_w >= 1600 and shortest_side >= 900:
        pixel_scale = 4
    elif shortest_side < 600:
        pixel_scale = 2
    else:
        pixel_scale = BROWSER_PIXEL_SCALE
    return RenderMetrics(
        screen_w,
        screen_h,
        max(INTERNAL_WIDTH, screen_w // pixel_scale),
        max(INTERNAL_HEIGHT, screen_h // pixel_scale),
        pixel_scale,
    )


def create_ui_fonts(screen_w: int, screen_h: int) -> dict[str, pygame.font.Font]:
    """Create anti-aliased fonts at final-window density, never world resolution."""
    del screen_w  # Height gives stable sizing across wide and narrow layouts.
    scale = max(0.85, min(1.0, screen_h / WINDOW_SIZE[1]))

    def make(size: int, *, bold: bool = False) -> pygame.font.Font:
        # Pygame's bundled font is available in Pygbag; system fonts such as
        # Consolas are not, and their browser fallback was visibly jagged.
        font = pygame.font.Font(None, max(14, round(size * scale)))
        font.set_bold(bold)
        return font

    return {
        "hud_title": make(36, bold=True),
        "ui": make(24),
        "helper": make(19),
        "dialogue": make(26),
        "menu": make(26),
        "title_screen": make(68, bold=True),
        "attitude_icon": make(20, bold=True),
        "recall_title": make(22, bold=True),
        "recall_body": make(19),
        "gossip_title": make(20, bold=True),
        "gossip_body": make(18),
        "tutorial_title": make(32, bold=True),
        "tutorial_body": make(22),
        "tutorial_small": make(18, bold=True),
    }


def compute_ui_layout(screen_w: int, screen_h: int) -> UILayout:
    margin = max(12, min(24, screen_w // 80))
    hud_height = max(112, min(126, screen_h // 5))
    hud = pygame.Rect(margin, margin, screen_w - margin * 2, hud_height)
    right_w = min(320, max(250, screen_w // 4))
    memory = pygame.Rect(screen_w - margin - right_w, hud.bottom + 12, right_w, 82)
    attitude_h = min(154, max(132, screen_h // 5))
    attitudes = pygame.Rect(
        screen_w - margin - right_w,
        memory.bottom + 10,
        right_w,
        attitude_h,
    )
    if screen_w < 1000:
        objective_w = max(280, min(420, screen_w - right_w - margin * 3))
        objective_x = margin
    else:
        objective_w = min(420, max(300, screen_w // 3))
        objective_x = (screen_w - objective_w) // 2
    objective = pygame.Rect(
        objective_x,
        hud.bottom + 12,
        objective_w,
        72,
    )
    dialogue_h = min(196, max(164, screen_h // 4))
    dialogue = pygame.Rect(
        margin,
        screen_h - margin - dialogue_h,
        screen_w - margin * 2,
        dialogue_h,
    )
    recall_w = min(500, max(360, screen_w - right_w - margin * 3))
    recall = pygame.Rect(margin, hud.bottom + 12, recall_w, 120)
    objective_with_recall = pygame.Rect(
        margin if screen_w < 1000 else max(margin, screen_w - margin - objective_w),
        recall.bottom + 12 if screen_w < 1000 else min(screen_h - 260, attitudes.bottom + 12),
        objective_w,
        72,
    )
    menu = pygame.Rect(margin, hud.bottom + 22, min(320, screen_w - margin * 2), 300)
    tutorial = pygame.Rect(
        margin * 2,
        margin * 2,
        screen_w - margin * 4,
        screen_h - margin * 4,
    )
    loading = pygame.Rect(0, 0, min(360, screen_w - margin * 2), 72)
    loading.center = (screen_w // 2, screen_h // 2)
    return UILayout(
        margin,
        hud,
        memory,
        attitudes,
        objective,
        objective_with_recall,
        dialogue,
        recall,
        menu,
        tutorial,
        loading,
    )


def get_attitude_color(attitude: str) -> tuple[int, int, int]:
    return ATTITUDE_COLORS.get(attitude, ATTITUDE_COLORS["neutral"])


def get_attitude_icon(attitude: str) -> str:
    return ATTITUDE_ICONS.get(attitude, ATTITUDE_ICONS["neutral"])


def attitude_summary_from_state(attitudes: dict[str, str]) -> str:
    return "\n".join(
        f"{ATTITUDE_NAMES[key]}: {attitudes.get(key, 'neutral')}"
        for key in ATTITUDE_NAMES
    )


def default_promise_state() -> dict[str, dict[str, Any]]:
    return {
        "mira_no_trouble": {
            "status": "not_made",
            "broken": False,
            "broken_summary": None,
            "callout_pending": False,
            "callout_delivered": False,
        }
    }


def mira_promise(promises: dict[str, Any]) -> dict[str, Any]:
    value = promises.get("mira_no_trouble") if isinstance(promises, dict) else None
    return dict(value) if isinstance(value, dict) else default_promise_state()["mira_no_trouble"]


def promise_context_for_npc(npc_key: str, promises: dict[str, Any]) -> str:
    if npc_key != "guard":
        return ""
    promise = mira_promise(promises)
    if promise.get("status") == "active":
        return "Player promised Captain Mira not to cause trouble."
    if promise.get("status") == "broken":
        summary = str(promise.get("broken_summary") or "caused trouble in the village")
        return f"Player promised Captain Mira not to cause trouble. Promise broken: {summary}."
    return ""


def pending_mira_callout(promises: dict[str, Any]) -> str:
    promise = mira_promise(promises)
    if not promise.get("callout_pending"):
        return ""
    summary = str(promise.get("broken_summary") or "caused trouble in the village")
    return f"Player broke their promise to Captain Mira: {summary}."


@dataclass(frozen=True)
class Building:
    name: str
    rect: pygame.Rect
    roof_color: tuple[int, int, int]


@dataclass
class VillageNPC:
    key: str
    display_name: str
    tile_pos: tuple[int, int]
    sprite: pygame.Surface
    interaction_label: str


def get_menu_options_for_npc(
    npc: VillageNPC | None,
    tutorial_state: dict | None = None,
    promises: dict[str, Any] | None = None,
) -> tuple[str, ...]:
    """Expose the no-trouble promise only to Mira before it has been made."""
    options = list(MENU_OPTIONS)
    if npc is not None and npc.key == "guard":
        promise = mira_promise(promises or {})
        tutorial_step = get_current_tutorial_step(tutorial_state or {})
        tutorial_allows_promise = not tutorial_is_active(tutorial_state or {}) or (
            tutorial_step is not None
            and tutorial_step.get("id") == "mira_promise"
            and not (tutorial_state or {}).get("popup_open")
        )
        if promise.get("status") == "not_made" and tutorial_allows_promise:
            options.insert(2, "Promise No Trouble")
    return tuple(options)


@dataclass
class Player:
    tile_pos: tuple[int, int]
    pixel_pos: pygame.Vector2
    target_tile: tuple[int, int]
    moving: bool = False
    facing: str = "down"


@dataclass
class BackendJob:
    action: str
    future: asyncio.Task
    npc: VillageNPC | None = None
    player_message: str = ""
    was_forgotten: bool = False


def start_backend_job(
    action: str,
    coro,
    npc: VillageNPC | None = None,
    player_message: str = "",
    was_forgotten: bool = False,
) -> BackendJob:
    """Schedule backend work without blocking rendering in either runtime."""
    return BackendJob(
        action,
        asyncio.create_task(coro),
        npc,
        player_message,
        was_forgotten,
    )


def wrap_text(
    text: str,
    font: pygame.font.Font,
    max_width: int,
) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def paginate_dialogue(text: str, font: pygame.font.Font) -> list[str]:
    lines = wrap_text(text, font, DIALOGUE_TEXT_WIDTH)
    if not lines:
        return [""]
    return [
        "\n".join(lines[index : index + DIALOGUE_MAX_LINES])
        for index in range(0, len(lines), DIALOGUE_MAX_LINES)
    ]


def build_local_memory_text(
    npc: VillageNPC,
    events: list[dict[str, Any]],
    allow_hearsay: bool = True,
    hearsay_session_id: str | None = None,
) -> str:
    """Read fast debug memory without triggering Cognee GRAPH_COMPLETION recall."""
    if npc.key == "elder":
        if not allow_hearsay:
            return (
                "No village gossip has reached Elder Voss yet. End Day lets "
                "stories travel."
            )
        hearsay: list[str] = []
        for event in events:
            if not isinstance(event, dict):
                continue
            if hearsay_session_id and event.get("session_id") != hearsay_session_id:
                continue
            npc_key = str(event.get("npc_key") or "")
            if npc_key not in {"blacksmith", "merchant", "guard"}:
                continue
            summary = str(
                (event.get("analysis") or {}).get("summary")
                if isinstance(event.get("analysis"), dict)
                else event.get("summary") or ""
            ).strip()
            if summary:
                hearsay.append(summary)
        return "\n".join(f"- {line}" for line in hearsay[-6:]) or (
            "No local debug memory found for this NPC."
        )

    direct_events = [
        event for event in events if event.get("npc_key") == npc.key
    ]
    if not direct_events:
        return "No local debug memory found for this NPC."

    interactions: list[str] = []
    for event in direct_events[-5:]:
        analysis = event.get("analysis")
        summary = str(
            analysis.get("summary") if isinstance(analysis, dict) else event.get("summary") or ""
        ).strip()
        interactions.append(summary or "Interaction stored in local debug memory.")
    return (
        f"Recent direct interactions with {npc.display_name}:\n\n"
        + "\n\n".join(interactions)
    )


def player_asks_about_memory(message: str) -> bool:
    normalized = message.casefold()
    return any(
        phrase in normalized
        for phrase in (
            "remember",
            "know me",
            "met me",
            "met before",
            "last time",
            "seen me",
        )
    )


def format_confession_message(message: str) -> str:
    """Give confession input an explicit semantic marker for the normal pipeline."""
    cleaned = " ".join(str(message or "").split()).strip()
    if cleaned.casefold().startswith("confession:"):
        return cleaned
    return f"Confession: {cleaned}"


def get_verified_npc_memory(
    npc_key: str,
    run_id: str,
    forgotten_npcs: set[str],
    met_npcs: set[str],
    memory_cutoffs: dict[str, int] | None = None,
    events: list[dict[str, Any]] | None = None,
) -> str:
    """Return factual current-run player statements, never model-generated lore."""
    if npc_key in forgotten_npcs or npc_key not in met_npcs:
        return ""

    run_session_prefix = f"{run_id}_day_"
    cutoff = (memory_cutoffs or {}).get(npc_key, 0)
    verified_facts: list[str] = []
    for event_index, event in enumerate(events or []):
        if event_index < cutoff or not isinstance(event, dict):
            continue
        session_id = str(event.get("session_id") or "")
        if not session_id.startswith(run_session_prefix):
            continue
        if event.get("npc_key") != npc_key:
            continue
        analysis = event.get("analysis")
        if isinstance(analysis, dict):
            summary = " ".join(str(analysis.get("summary") or "").split())
            if summary:
                verified_facts.append(f"- {summary[:240]}")
                continue
        player_message = " ".join(
            str(event.get("player_message") or "").split()
        )
        if not player_message:
            continue
        verified_facts.append(f'- Player previously said: "{player_message[:220]}"')

    return "\n".join(verified_facts[-6:])


def ambient_gossip_line(npc_key: str, summary: str, analysis: dict) -> str:
    """Turn one real event summary into short, source-free village chatter."""
    label = compact_recall_summary(summary, analysis)
    npc_lines = {
        ("blacksmith", "fair payment"): "Fair coin changed hands at the forge.",
        ("blacksmith", "fair trade"): "Gareth called it a fair trade.",
        ("blacksmith", "insult"): "Gareth's craft was insulted.",
        ("merchant", "aggressive bargain"): "Petra heard a hard bargain.",
        ("merchant", "found it pricey"): "Petra wasn't pleased with the price talk.",
        ("merchant", "fair payment"): "Petra made a fair sale.",
        ("guard", "evasive denial"): "Mira heard an evasive denial.",
        ("guard", "suspicious denial"): "Mira thought the story sounded doubtful.",
        ("guard", "honest confession"): "Mira heard an honest confession.",
        ("elder", "honest confession"): "Voss heard an honest confession.",
    }
    if (npc_key, label) in npc_lines:
        return npc_lines[(npc_key, label)]

    general_lines = {
        "friendly meeting": "Kind words went around.",
        "purchase interest": "Someone was looking to buy.",
        "apology": "An apology was offered.",
        "bribe attempt": "Someone tried to buy silence.",
        "neutral question": "A curious question was asked.",
        "no prior memory": "A new story began tonight.",
    }
    if label in general_lines:
        return general_lines[label]
    return label[:1].upper() + label[1:].rstrip(".") + "."


def build_gossip_chatter_lines(
    run_id: str,
    events: list[dict[str, Any]],
) -> list[str]:
    """Build ambient chatter from current-run events without source arrows."""
    valid_npcs = {"blacksmith", "merchant", "guard", "elder"}
    chatter_lines: list[str] = []
    seen: set[str] = set()

    for event in events:
        if not isinstance(event, dict):
            continue
        session_id = str(event.get("session_id") or "")
        if not session_id.startswith(run_id):
            continue
        npc_key = str(event.get("npc_key") or "").casefold().strip()
        if not npc_key or npc_key not in valid_npcs:
            continue

        summary = ""
        analysis = event.get("analysis")
        if isinstance(analysis, dict):
            summary = " ".join(str(analysis.get("summary") or "").split())
        if not summary:
            for field in ("summary", "description"):
                summary = " ".join(str(event.get(field) or "").split())
                if summary:
                    break
        if not summary:
            continue

        summary = summary[:180]
        analysis_data = analysis if isinstance(analysis, dict) else {}
        chatter = ambient_gossip_line(npc_key, summary, analysis_data)
        dedupe_key = chatter.casefold()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        chatter_lines.append(chatter)

    if chatter_lines:
        return (chatter_lines[-5:] + ["The village remembers."])[-6:]
    return ["Quiet night in the village.", "No new stories tonight."]


def create_buildings() -> list[Building]:
    return [
        Building(
            "Blacksmith Shop",
            pygame.Rect(3, 2, 5, 4),
            (142, 67, 48),
        ),
        Building(
            "Guard Post",
            pygame.Rect(22, 2, 5, 4),
            (66, 91, 131),
        ),
        Building(
            "Merchant Shop",
            pygame.Rect(2, 12, 5, 4),
            (165, 92, 130),
        ),
        Building(
            "Elder Hall",
            pygame.Rect(12, 17, 6, 4),
            (106, 79, 135),
        ),
    ]


def create_village_map() -> list[list[str]]:
    """Build the grass, path, and tree layer for the extended 40x22 village."""
    tile_map = [["grass" for _ in range(MAP_WIDTH)] for _ in range(MAP_HEIGHT)]

    # Main crossing and short branches to every NPC doorstep.
    for x in range(1, MAP_WIDTH - 1):
        tile_map[10][x] = "path"
    for y in range(1, MAP_HEIGHT - 1):
        tile_map[y][14] = "path"

    path_branches = (
        ((5, y) for y in range(6, 11)),
        ((24, y) for y in range(6, 11)),
        ((7, y) for y in range(10, 14)),
        ((14, y) for y in range(11, 17)),
        # Eastern commons: a path continues beyond Mira's post so the camera
        # can travel past her instead of pinning her under the right HUD.
        ((x, 6) for x in range(24, 35)),
        ((34, y) for y in range(6, 16)),
        ((x, 15) for x in range(30, 38)),
    )
    for branch in path_branches:
        for x, y in branch:
            tile_map[y][x] = "path"

    # A tree border frames the village. Interior clusters create visual pockets.
    for x in range(MAP_WIDTH):
        tile_map[0][x] = "tree"
        tile_map[MAP_HEIGHT - 1][x] = "tree"
    for y in range(MAP_HEIGHT):
        tile_map[y][0] = "tree"
        tile_map[y][MAP_WIDTH - 1] = "tree"

    tree_clusters = (
        (1, 3),
        (1, 5),
        (9, 2),
        (10, 3),
        (18, 2),
        (19, 3),
        (28, 4),
        (31, 3),
        (36, 2),
        (38, 5),
        (30, 8),
        (37, 8),
        (32, 12),
        (37, 13),
        (30, 17),
        (34, 18),
        (38, 18),
        (9, 7),
        (19, 7),
        (10, 14),
        (19, 14),
        (2, 18),
        (3, 19),
        (9, 18),
        (10, 19),
        (20, 18),
        (21, 19),
        (27, 18),
        (28, 17),
    )
    for x, y in tree_clusters:
        tile_map[y][x] = "tree"

    return tile_map


def create_player_sprites() -> dict[str, pygame.Surface]:
    """Create clear facing variants from the original player sprite."""
    down = make_player_sprite(TILE_SIZE)

    up = down.copy()
    pygame.draw.rect(up, (229, 181, 129), (5, 3, 6, 5))
    pygame.draw.rect(up, (84, 54, 38), (5, 2, 6, 5))
    pygame.draw.rect(up, (112, 73, 43), (6, 8, 5, 4))
    pygame.draw.rect(up, (72, 46, 34), (7, 8, 3, 1))

    right = down.copy()
    pygame.draw.rect(right, (229, 181, 129), (5, 3, 6, 5))
    pygame.draw.rect(right, (84, 54, 38), (5, 2, 6, 2))
    pygame.draw.rect(right, (84, 54, 38), (5, 3, 2, 2))
    pygame.draw.rect(right, (38, 40, 43), (10, 5, 1, 1))
    pygame.draw.rect(right, (188, 53, 47), (4, 7, 2, 2))
    left = pygame.transform.flip(right, True, False)

    return {"up": up, "down": down, "left": left, "right": right}


def create_npcs() -> list[VillageNPC]:
    npcs = [
        VillageNPC(
            key="blacksmith",
            display_name="Gareth the Blacksmith",
            tile_pos=(5, 6),
            sprite=make_npc_sprite(TILE_SIZE, (148, 75, 49), apron=True),
            interaction_label="Gareth's forge",
        ),
        VillageNPC(
            key="guard",
            display_name="Captain Mira the Guard",
            tile_pos=(24, 6),
            sprite=make_npc_sprite(TILE_SIZE, (65, 92, 145), helmet=True),
            interaction_label="Mira's guard post",
        ),
        VillageNPC(
            key="merchant",
            display_name="Petra the Merchant",
            tile_pos=(7, 13),
            sprite=make_npc_sprite(TILE_SIZE, (177, 80, 126), apron=True),
            interaction_label="Petra's market stall",
        ),
        VillageNPC(
            key="elder",
            display_name="Elder Voss",
            tile_pos=(14, 16),
            sprite=make_npc_sprite(TILE_SIZE, (105, 75, 137), elder=True),
            interaction_label="Elder Voss's hall",
        ),
    ]
    validate_important_npc_safe_zone(npcs)
    return npcs


def validate_important_npc_safe_zone(npcs: list[VillageNPC]) -> None:
    """Keep key NPC homes out of the map's rightmost HUD-buffer tiles."""
    important_keys = {"blacksmith", "merchant", "guard", "elder"}
    safe_limit = MAP_WIDTH - RIGHT_UI_SAFE_MARGIN_TILES
    unsafe = [
        npc.display_name
        for npc in npcs
        if npc.key in important_keys and npc.tile_pos[0] >= safe_limit
    ]
    if unsafe:
        raise ValueError(
            "Important NPCs must stay left of the right UI safe zone: "
            + ", ".join(unsafe)
        )


def build_blocked_tiles(
    tile_map: list[list[str]],
    buildings: list[Building],
    npcs: list[VillageNPC],
) -> set[tuple[int, int]]:
    blocked = {
        (x, y)
        for y, row in enumerate(tile_map)
        for x, tile_name in enumerate(row)
        if tile_name == "tree"
    }
    for building in buildings:
        for y in range(building.rect.top, building.rect.bottom):
            for x in range(building.rect.left, building.rect.right):
                blocked.add((x, y))
    blocked.update(npc.tile_pos for npc in npcs)
    return blocked


def get_nearby_npc(
    player_tile: tuple[int, int],
    npcs: list[VillageNPC],
) -> VillageNPC | None:
    player_x, player_y = player_tile
    for npc in npcs:
        npc_x, npc_y = npc.tile_pos
        if abs(player_x - npc_x) + abs(player_y - npc_y) == 1:
            return npc
    return None


def held_direction(keys: pygame.key.ScancodeWrapper) -> tuple[int, int, str] | None:
    if keys[pygame.K_UP] or keys[pygame.K_w]:
        return (0, -1, "up")
    if keys[pygame.K_DOWN] or keys[pygame.K_s]:
        return (0, 1, "down")
    if keys[pygame.K_LEFT] or keys[pygame.K_a]:
        return (-1, 0, "left")
    if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
        return (1, 0, "right")
    return None


def try_start_player_move(
    player: Player,
    direction: tuple[int, int, str],
    blocked_tiles: set[tuple[int, int]],
) -> None:
    if player.moving:
        return
    dx, dy, facing = direction
    player.facing = facing
    destination = (player.tile_pos[0] + dx, player.tile_pos[1] + dy)
    destination_in_bounds = (
        0 <= destination[0] < MAP_WIDTH and 0 <= destination[1] < MAP_HEIGHT
    )
    if destination_in_bounds and destination not in blocked_tiles:
        player.target_tile = destination
        player.moving = True


def update_player(player: Player, delta_seconds: float) -> None:
    if not player.moving:
        return

    target_pixel = pygame.Vector2(
        player.target_tile[0] * TILE_SIZE,
        player.target_tile[1] * TILE_SIZE,
    )
    offset = target_pixel - player.pixel_pos
    step = PLAYER_SPEED * delta_seconds
    if offset.length() <= step:
        player.pixel_pos = target_pixel
        player.tile_pos = player.target_tile
        player.moving = False
    else:
        player.pixel_pos += offset.normalize() * step


def camera_for_player(
    player: Player,
    viewport_width: int,
    viewport_height: int,
) -> pygame.Vector2:
    player_center_x = player.pixel_pos.x + TILE_SIZE / 2
    player_center_y = player.pixel_pos.y + TILE_SIZE / 2
    world_pixel_width = MAP_WIDTH * TILE_SIZE
    max_camera_x = max(0, world_pixel_width - viewport_width)
    max_camera_y = max(0, MAP_HEIGHT * TILE_SIZE - viewport_height)
    return pygame.Vector2(
        max(0, min(max_camera_x, player_center_x - viewport_width / 2)),
        max(0, min(max_camera_y, player_center_y - viewport_height / 2)),
    )


def smoothstep(progress: float) -> float:
    """Ease temporary gathering movement without changing NPC home tiles."""
    progress = max(0.0, min(1.0, progress))
    return progress * progress * (3.0 - 2.0 * progress)


def get_endday_npc_positions(
    npcs: list[VillageNPC],
    animation_progress: float,
    elapsed_ms: int,
) -> dict[str, pygame.Vector2]:
    """Return temporary world positions for gather, chatter, and return phases."""
    progress = max(0.0, min(1.0, animation_progress))
    if progress < 0.18:
        gather_amount = 0.0
    elif progress < 0.40:
        gather_amount = smoothstep((progress - 0.18) / 0.22)
    elif progress < 0.70:
        gather_amount = 1.0
    elif progress < 0.95:
        gather_amount = 1.0 - smoothstep((progress - 0.70) / 0.25)
    else:
        gather_amount = 0.0

    positions: dict[str, pygame.Vector2] = {}
    for index, npc in enumerate(npcs):
        home = pygame.Vector2(
            npc.tile_pos[0] * TILE_SIZE,
            npc.tile_pos[1] * TILE_SIZE,
        )
        gather_tile = ENDDAY_GATHER_TILES.get(npc.key, npc.tile_pos)
        gathering = pygame.Vector2(
            gather_tile[0] * TILE_SIZE,
            gather_tile[1] * TILE_SIZE,
        )
        position = home.lerp(gathering, gather_amount)
        if 0.40 <= progress < 0.70:
            position.y += math.sin(elapsed_ms * 0.008 + index * 1.7) * 0.8
        positions[npc.key] = position
    return positions


def draw_buildings(
    surface: pygame.Surface,
    camera: pygame.Vector2,
    buildings: list[Building],
    roof_tiles: dict[tuple[int, int, int], pygame.Surface],
    wall_tile: pygame.Surface,
) -> None:
    for building in buildings:
        for local_y in range(building.rect.height):
            for local_x in range(building.rect.width):
                world_x = (building.rect.x + local_x) * TILE_SIZE
                world_y = (building.rect.y + local_y) * TILE_SIZE
                screen_pos = (int(world_x - camera.x), int(world_y - camera.y))
                tile = roof_tiles[building.roof_color] if local_y < 2 else wall_tile
                surface.blit(tile, screen_pos)

        # One painted door makes each building read clearly as a destination.
        door_tile_x = building.rect.x + building.rect.width // 2
        door_tile_y = building.rect.bottom - 1
        door_x = int(door_tile_x * TILE_SIZE - camera.x + 5)
        door_y = int(door_tile_y * TILE_SIZE - camera.y + 5)
        pygame.draw.rect(surface, (91, 57, 39), (door_x, door_y, 7, 11))
        pygame.draw.rect(surface, (133, 82, 46), (door_x + 1, door_y + 1, 5, 10))
        pygame.draw.rect(surface, (235, 193, 87), (door_x + 5, door_y + 6, 1, 1))


def draw_shop_displays(
    surface: pygame.Surface,
    camera: pygame.Vector2,
) -> None:
    """Draw decorative, non-interactive wares beside Gareth and Petra."""
    # Gareth's low wooden weapon rack: sword, dagger, shield, and tiny tags.
    forge_x = round(6.2 * TILE_SIZE - camera.x)
    forge_y = round(6.8 * TILE_SIZE - camera.y)
    pygame.draw.rect(surface, (71, 43, 29), (forge_x, forge_y + 8, 34, 10))
    pygame.draw.rect(surface, (137, 85, 43), (forge_x - 1, forge_y + 5, 36, 6))
    pygame.draw.rect(surface, (78, 46, 29), (forge_x + 3, forge_y + 17, 4, 6))
    pygame.draw.rect(surface, (78, 46, 29), (forge_x + 28, forge_y + 17, 4, 6))
    pygame.draw.line(
        surface,
        (218, 225, 219),
        (forge_x + 5, forge_y + 3),
        (forge_x + 14, forge_y - 5),
        2,
    )
    pygame.draw.line(
        surface,
        (112, 73, 44),
        (forge_x + 4, forge_y + 4),
        (forge_x + 8, forge_y + 1),
        2,
    )
    pygame.draw.line(
        surface,
        (205, 214, 210),
        (forge_x + 17, forge_y + 3),
        (forge_x + 22, forge_y - 2),
        2,
    )
    pygame.draw.circle(surface, (73, 88, 102), (forge_x + 29, forge_y), 5)
    pygame.draw.circle(surface, (185, 194, 185), (forge_x + 29, forge_y), 5, 1)
    for tag_x in (4, 16, 27):
        pygame.draw.rect(surface, (231, 213, 142), (forge_x + tag_x, forge_y + 12, 5, 3))
        pygame.draw.rect(surface, (91, 66, 39), (forge_x + tag_x + 2, forge_y + 13, 1, 1))

    # Petra's colorful general-goods table: sack, jar, cloth, fruit, bottles.
    stall_x = round(8.2 * TILE_SIZE - camera.x)
    stall_y = round(12.3 * TILE_SIZE - camera.y)
    pygame.draw.rect(surface, (76, 47, 31), (stall_x, stall_y + 10, 38, 10))
    pygame.draw.rect(surface, (153, 91, 48), (stall_x - 1, stall_y + 7, 40, 6))
    pygame.draw.circle(surface, (193, 157, 91), (stall_x + 6, stall_y + 5), 5)
    pygame.draw.rect(surface, (105, 171, 169), (stall_x + 13, stall_y, 6, 8))
    pygame.draw.rect(surface, (216, 224, 205), (stall_x + 14, stall_y + 1, 4, 2))
    pygame.draw.rect(surface, (151, 71, 123), (stall_x + 21, stall_y + 2, 8, 6))
    pygame.draw.circle(surface, (210, 82, 55), (stall_x + 33, stall_y + 4), 4)
    pygame.draw.rect(surface, (74, 130, 72), (stall_x + 33, stall_y - 1, 1, 3))
    for tag_x in (3, 14, 25, 33):
        pygame.draw.rect(surface, (238, 220, 154), (stall_x + tag_x, stall_y + 14, 4, 3))
        pygame.draw.rect(surface, (92, 66, 39), (stall_x + tag_x + 1, stall_y + 15, 1, 1))


def draw_world(
    surface: pygame.Surface,
    tile_map: list[list[str]],
    buildings: list[Building],
    npcs: list[VillageNPC],
    player: Player,
    player_sprites: dict[str, pygame.Surface],
    tile_assets: dict[str, pygame.Surface],
    roof_tiles: dict[tuple[int, int, int], pygame.Surface],
    wall_tile: pygame.Surface,
    alert_bubble: pygame.Surface,
    nearby_npc: VillageNPC | None,
    npc_positions: dict[str, pygame.Vector2] | None = None,
    show_player: bool = True,
) -> pygame.Vector2:
    viewport_width, viewport_height = surface.get_size()
    camera = camera_for_player(player, viewport_width, viewport_height)
    surface.fill((31, 63, 49))

    for y, row in enumerate(tile_map):
        for x, tile_name in enumerate(row):
            screen_x = int(x * TILE_SIZE - camera.x)
            screen_y = int(y * TILE_SIZE - camera.y)
            if (
                screen_x <= -TILE_SIZE
                or screen_y <= -TILE_SIZE
                or screen_x >= viewport_width
                or screen_y >= viewport_height
            ):
                continue
            surface.blit(tile_assets[tile_name], (screen_x, screen_y))

    draw_buildings(surface, camera, buildings, roof_tiles, wall_tile)
    draw_shop_displays(surface, camera)

    # Depth-sort characters by their feet so crossings feel properly top-down.
    actors: list[tuple[float, pygame.Surface, tuple[int, int]]] = []
    for npc in npcs:
        npc_pixel = (
            npc_positions[npc.key]
            if npc_positions is not None and npc.key in npc_positions
            else pygame.Vector2(
                npc.tile_pos[0] * TILE_SIZE,
                npc.tile_pos[1] * TILE_SIZE,
            )
        )
        npc_x = int(npc_pixel.x - camera.x)
        npc_y = int(npc_pixel.y - camera.y)
        actors.append((npc_pixel.y, npc.sprite, (npc_x, npc_y)))
    if show_player:
        player_screen_pos = (
            int(player.pixel_pos.x - camera.x),
            int(player.pixel_pos.y - camera.y),
        )
        actors.append(
            (
                player.pixel_pos.y,
                player_sprites[player.facing],
                player_screen_pos,
            )
        )
    for _, sprite, position in sorted(actors, key=lambda actor: actor[0]):
        surface.blit(sprite, position)

    if nearby_npc is not None:
        bubble_x = int(nearby_npc.tile_pos[0] * TILE_SIZE - camera.x)
        bubble_y = int(nearby_npc.tile_pos[1] * TILE_SIZE - camera.y - 13)
        surface.blit(alert_bubble, (bubble_x, bubble_y))

    return camera


def memory_status_label(last_api_event: str) -> str:
    event = last_api_event.casefold()
    if "promise broken" in event:
        return "promise broken"
    if "promise remembered" in event:
        return "promise remembered"
    if "confess + remember" in event:
        return "confess + remember()"
    if "recalling memory" in event:
        return "recalling..."
    if "recall trace" in event:
        return "trace shown"
    if (
        "recall()" in event
        or "remember()" in event
        or "waiting for" in event
        or "talk failed" in event
    ):
        return "recall() + remember()"
    if "improve()" in event or "gossip" in event or "end day" in event:
        return "improve() + gossip"
    if "forget()" in event or "dataset rotation" in event or "bribe" in event:
        return "forget() / rotation"
    if "local debug memory" in event:
        return "local debug memory"
    return "No action yet"


def draw_npc_attitude_icons(
    surface: pygame.Surface,
    npcs: list[VillageNPC],
    camera: pygame.Vector2,
    npc_attitudes: dict[str, str],
    font: pygame.font.Font,
    world_scale: tuple[float, float],
) -> None:
    scale_x, scale_y = world_scale
    for npc in npcs:
        npc_screen_x = (npc.tile_pos[0] * TILE_SIZE - camera.x) * scale_x
        npc_screen_y = (npc.tile_pos[1] * TILE_SIZE - camera.y) * scale_y
        badge = pygame.Rect(0, 0, 26, 26)
        badge.center = (round(npc_screen_x + 60), round(npc_screen_y + 2))
        if not surface.get_rect().colliderect(badge):
            continue

        attitude = npc_attitudes.get(npc.key, "neutral")
        attitude_color = get_attitude_color(attitude)
        pygame.draw.rect(surface, (14, 19, 26), badge)
        pygame.draw.rect(surface, attitude_color, badge, 2)
        icon_image = font.render(
            get_attitude_icon(attitude),
            True,
            attitude_color,
        )
        surface.blit(icon_image, icon_image.get_rect(center=badge.center))


def draw_village_attitude_panel(
    surface: pygame.Surface,
    summary: str,
    font: pygame.font.Font,
) -> None:
    panel = compute_ui_layout(*surface.get_size()).attitudes
    pygame.draw.rect(surface, (13, 18, 24), panel)
    pygame.draw.rect(surface, (220, 205, 157), panel, 3)
    pygame.draw.rect(surface, (73, 85, 84), panel.inflate(-8, -8), 1)

    title_image = font.render("Village Attitude", True, (247, 205, 104))
    surface.blit(title_image, (panel.x + 12, panel.y + 9))

    for index, line in enumerate(summary.splitlines()[:5]):
        _, _, attitude = line.rpartition(": ")
        attitude_color = get_attitude_color(attitude)
        icon = get_attitude_icon(attitude)
        line_image = font.render(f"{icon} {line}", True, attitude_color)
        surface.blit(
            line_image,
            (panel.x + 12, panel.y + 38 + index * font.get_linesize()),
        )


def draw_hud(
    surface: pygame.Surface,
    nearby_npc: VillageNPC | None,
    npc_attitudes: dict[str, str],
    day: int,
    last_api_event: str,
    title_font: pygame.font.Font,
    ui_font: pygame.font.Font,
    small_font: pygame.font.Font,
) -> None:
    screen_w, screen_h = surface.get_size()
    layout = compute_ui_layout(screen_w, screen_h)
    panel = layout.hud
    pygame.draw.rect(surface, (13, 18, 24), panel)
    pygame.draw.rect(surface, (220, 205, 157), panel, 3)
    pygame.draw.rect(surface, (73, 85, 84), panel.inflate(-12, -12), 2)

    title_image = title_font.render("EchoWorld", True, (247, 205, 104))
    day_image = ui_font.render(f"Day {day}", True, (237, 237, 220))
    nearby_text = nearby_npc.display_name if nearby_npc else "None"
    nearby_image = ui_font.render(
        f"Nearby: {nearby_text}",
        True,
        (198, 218, 190),
    )
    controls = small_font.render(
        "Move: WASD/Arrows | Interact: E | End Day: N | Reset: R | Esc: Cancel",
        True,
        (181, 190, 185),
    )

    content_x = panel.x + 18
    surface.blit(title_image, (content_x, panel.y + 12))
    surface.blit(day_image, (content_x + min(250, panel.width // 4), panel.y + 20))
    surface.blit(nearby_image, (content_x, panel.y + 58))
    if nearby_npc is not None:
        nearby_attitude = npc_attitudes.get(nearby_npc.key, "neutral")
        attitude_image = ui_font.render(
            f"Attitude: {nearby_attitude}",
            True,
            get_attitude_color(nearby_attitude),
        )
        attitude_x = min(panel.right - attitude_image.get_width() - 18, content_x + 534)
        surface.blit(attitude_image, (attitude_x, panel.y + 58))
    controls_text = (
        "Move: WASD/Arrows | E: Interact | N: End Day | R: Reset | Esc: Cancel"
        if screen_w < 1100
        else "Move: WASD/Arrows | Interact: E | End Day: N | Reset: R | Esc: Cancel"
    )
    controls = small_font.render(controls_text, True, (181, 190, 185))
    surface.blit(controls, (content_x, panel.bottom - controls.get_height() - 10))

    status_panel = layout.memory
    pygame.draw.rect(surface, (13, 18, 24), status_panel)
    pygame.draw.rect(surface, (220, 205, 157), status_panel, 3)
    pygame.draw.rect(surface, (73, 85, 84), status_panel.inflate(-8, -8), 1)
    status_title = small_font.render("Memory", True, (247, 205, 104))
    surface.blit(status_title, (status_panel.x + 12, status_panel.y + 9))

    status_text = memory_status_label(last_api_event)
    status_image = small_font.render(status_text, True, (198, 218, 190))
    surface.blit(status_image, (status_panel.x + 12, status_panel.y + 43))


def draw_interaction_hint(
    surface: pygame.Surface,
    nearby_npc: VillageNPC,
    small_font: pygame.font.Font,
) -> None:
    hint = f"Press E to talk to {nearby_npc.display_name}"
    hint_image = small_font.render(hint, True, (247, 241, 213))
    box = hint_image.get_rect()
    box.width += 28
    box.height += 20
    screen_w, screen_h = surface.get_size()
    layout = compute_ui_layout(screen_w, screen_h)
    box.centerx = screen_w // 2
    box.bottom = layout.dialogue.y - 12
    pygame.draw.rect(surface, (16, 20, 28), box)
    pygame.draw.rect(surface, (224, 207, 154), box, 3)
    surface.blit(hint_image, (box.x + 14, box.y + 10))


def draw_title_screen(
    surface: pygame.Surface,
    title_font: pygame.font.Font,
    subtitle_font: pygame.font.Font,
    prompt_font: pygame.font.Font,
) -> None:
    screen_w, screen_h = surface.get_size()
    layout = compute_ui_layout(screen_w, screen_h)
    surface.fill((12, 22, 24))
    for y in range(0, screen_h, 48):
        for x in range(0, screen_w, 48):
            color = (18, 45, 37) if (x // 48 + y // 48) % 2 == 0 else (20, 51, 41)
            pygame.draw.rect(surface, color, (x, y, 48, 48))

    panel_w = min(900, screen_w - layout.margin * 4)
    panel_h = min(520, screen_h - layout.margin * 4)
    panel = pygame.Rect(0, 0, panel_w, panel_h)
    panel.center = (screen_w // 2, screen_h // 2)
    pygame.draw.rect(surface, (14, 19, 26), panel)
    pygame.draw.rect(surface, (230, 210, 150), panel, 5)
    pygame.draw.rect(surface, (76, 91, 86), panel.inflate(-18, -18), 3)

    title_image = title_font.render("EchoWorld", True, (247, 205, 104))
    description = (
        "A memory-driven RPG where NPCs remember, gossip, forgive, and hold "
        "promises against you."
    )
    description_lines = wrap_text(description, subtitle_font, panel.width - 110)
    powered_image = subtitle_font.render(
        "Powered by Cognee.", True, (95, 235, 210)
    )
    prompt_color = (
        (247, 241, 213)
        if (pygame.time.get_ticks() // 550) % 2 == 0
        else (159, 167, 156)
    )
    prompt_image = prompt_font.render(
        "Press Enter to begin the guided demo.",
        True,
        prompt_color,
    )
    fullscreen_image = prompt_font.render(
        "Best viewed fullscreen.", True, (198, 218, 190)
    )
    footer_image = prompt_font.render(
        "Built for the WeMakeDevs x Cognee Hackathon",
        True,
        (173, 181, 169),
    )
    escape_image = prompt_font.render("Esc: Quit", True, (159, 167, 156))

    surface.blit(
        title_image,
        title_image.get_rect(center=(panel.centerx, panel.y + panel_h * 0.18)),
    )
    description_y = panel.y + round(panel_h * 0.34)
    for index, line in enumerate(description_lines[:3]):
        line_image = subtitle_font.render(line, True, (225, 230, 213))
        surface.blit(
            line_image,
            line_image.get_rect(
                center=(
                    panel.centerx,
                    description_y + index * subtitle_font.get_linesize(),
                )
            ),
        )
    surface.blit(
        powered_image,
        powered_image.get_rect(center=(panel.centerx, panel.y + panel_h * 0.53)),
    )
    surface.blit(
        prompt_image,
        prompt_image.get_rect(center=(panel.centerx, panel.y + panel_h * 0.68)),
    )
    surface.blit(
        fullscreen_image,
        fullscreen_image.get_rect(center=(panel.centerx, panel.y + panel_h * 0.76)),
    )
    surface.blit(
        footer_image,
        footer_image.get_rect(center=(panel.centerx, panel.y + panel_h * 0.89)),
    )
    surface.blit(
        escape_image,
        escape_image.get_rect(center=(panel.centerx, panel.y + panel_h * 0.96)),
    )


def draw_loading_overlay(
    surface: pygame.Surface,
    message: str,
    font: pygame.font.Font,
) -> None:
    panel = compute_ui_layout(*surface.get_size()).loading
    pygame.draw.rect(surface, (14, 19, 26), panel)
    pygame.draw.rect(surface, (230, 210, 150), panel, 4)
    pygame.draw.rect(surface, (76, 91, 86), panel.inflate(-12, -12), 2)
    image = font.render(message, True, (247, 241, 213))
    surface.blit(image, image.get_rect(center=panel.center))


def draw_echo_guide_portrait(surface: pygame.Surface, rect: pygame.Rect) -> None:
    """Draw an original Cognee-themed memory-guide portrait."""
    pygame.draw.rect(surface, (8, 24, 35), rect, border_radius=18)
    pygame.draw.rect(surface, (42, 208, 186), rect, 3, border_radius=18)
    glow = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.circle(glow, (48, 213, 203, 38), (rect.width // 2, 145), 100)
    surface.blit(glow, rect.topleft)

    center_x = rect.centerx
    pygame.draw.line(
        surface,
        (103, 226, 211),
        (center_x, rect.y + 65),
        (center_x, rect.y + 41),
        5,
    )
    pygame.draw.circle(surface, (173, 255, 232), (center_x, rect.y + 35), 8)
    pygame.draw.circle(surface, (29, 165, 168), (center_x, rect.y + 35), 4)

    head = pygame.Rect(center_x - 70, rect.y + 66, 140, 120)
    pygame.draw.rect(surface, (220, 244, 238), head, border_radius=36)
    pygame.draw.rect(surface, (47, 184, 177), head, 6, border_radius=36)
    visor = pygame.Rect(center_x - 51, rect.y + 103, 102, 45)
    pygame.draw.rect(surface, (10, 46, 65), visor, border_radius=19)
    pygame.draw.rect(surface, (73, 233, 211), visor, 3, border_radius=19)
    pygame.draw.circle(surface, (167, 255, 236), (center_x - 25, rect.y + 125), 7)
    pygame.draw.circle(surface, (167, 255, 236), (center_x + 25, rect.y + 125), 7)
    pygame.draw.arc(
        surface,
        (83, 214, 191),
        pygame.Rect(center_x - 18, rect.y + 143, 36, 20),
        0.15,
        math.pi - 0.15,
        3,
    )

    body = [
        (center_x - 76, rect.y + 205),
        (center_x + 76, rect.y + 205),
        (center_x + 95, rect.y + 340),
        (center_x - 95, rect.y + 340),
    ]
    pygame.draw.polygon(surface, (20, 103, 123), body)
    pygame.draw.lines(surface, (78, 226, 202), True, body, 5)
    pygame.draw.polygon(
        surface,
        (232, 251, 242),
        [
            (center_x - 26, rect.y + 206),
            (center_x + 26, rect.y + 206),
            (center_x + 14, rect.y + 273),
            (center_x, rect.y + 292),
            (center_x - 14, rect.y + 273),
        ],
    )
    pygame.draw.circle(surface, (66, 237, 196), (center_x, rect.y + 247), 12)
    pygame.draw.circle(surface, (211, 255, 238), (center_x, rect.y + 247), 5)

    # Orbiting memory nodes make the guide read as an agent, not a fantasy mascot.
    for node_x, node_y in (
        (rect.x + 35, rect.y + 78),
        (rect.right - 34, rect.y + 102),
        (rect.x + 29, rect.y + 285),
        (rect.right - 30, rect.y + 306),
    ):
        pygame.draw.line(surface, (34, 130, 145), (center_x, rect.y + 247), (node_x, node_y), 2)
        pygame.draw.circle(surface, (45, 212, 191), (node_x, node_y), 9)
        pygame.draw.circle(surface, (221, 255, 242), (node_x, node_y), 3)


def draw_tutorial_popup(
    surface: pygame.Surface,
    page: dict,
    title_font: pygame.font.Font,
    body_font: pygame.font.Font,
    small_font: pygame.font.Font,
) -> None:
    """Draw the modal Echo Guide onboarding card above every game layer."""
    screen_w, screen_h = surface.get_size()
    layout = compute_ui_layout(screen_w, screen_h)
    shade = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    shade.fill((2, 8, 16, 190))
    surface.blit(shade, (0, 0))

    panel = layout.tutorial.copy()
    panel.width = min(panel.width, 1040)
    panel.height = min(panel.height, 620)
    panel.center = (screen_w // 2, screen_h // 2)
    pygame.draw.rect(surface, (8, 19, 29), panel, border_radius=22)
    pygame.draw.rect(surface, (87, 231, 205), panel, 5, border_radius=22)
    pygame.draw.rect(surface, (37, 91, 104), panel.inflate(-18, -18), 2, border_radius=16)

    portrait_width = max(210, min(280, round(panel.width * 0.29)))
    portrait_rect = pygame.Rect(
        panel.x + 24,
        panel.y + 28,
        portrait_width,
        max(330, panel.height - 114),
    )
    draw_echo_guide_portrait(surface, portrait_rect)
    name_plate = pygame.Rect(
        portrait_rect.x + 12,
        portrait_rect.bottom + 8,
        portrait_rect.width - 24,
        38,
    )
    pygame.draw.rect(surface, (14, 65, 79), name_plate, border_radius=10)
    pygame.draw.rect(surface, (82, 224, 204), name_plate, 2, border_radius=10)
    name_image = small_font.render("ECHO GUIDE", True, (225, 255, 244))
    surface.blit(name_image, name_image.get_rect(center=name_plate.center))

    speech_x = portrait_rect.right + 26
    speech = pygame.Rect(
        speech_x,
        panel.y + 32,
        panel.right - speech_x - 24,
        panel.height - 102,
    )
    pygame.draw.rect(surface, (230, 247, 241), speech, border_radius=18)
    pygame.draw.rect(surface, (67, 204, 190), speech, 4, border_radius=18)
    pygame.draw.polygon(
        surface,
        (230, 247, 241),
        [(speech.x, speech.y + 112), (speech.x - 24, speech.y + 130), (speech.x, speech.y + 145)],
    )
    title = str(page.get("title") or "Echo Guide")
    title_image = title_font.render(title, True, (9, 64, 77))
    surface.blit(title_image, (speech.x + 24, speech.y + 22))

    body = " ".join(str(page.get("body") or "").split())
    max_body_lines = max(5, (speech.height - 110) // (body_font.get_linesize() + 3))
    body_lines = wrap_text(body, body_font, speech.width - 48)[:max_body_lines]
    line_y = speech.y + 78
    for line in body_lines:
        line_image = body_font.render(line, True, (20, 42, 49))
        surface.blit(line_image, (speech.x + 24, line_y))
        line_y += body_font.get_linesize() + 3

    page_count = int(page.get("page_count") or 1)
    page_index = int(page.get("page_index") or 0)
    page_hint = f"  {page_index + 1}/{page_count}" if page_count > 1 else ""
    footer = small_font.render(
        f"Enter / Space / E: Continue{page_hint}    S: Skip Tutorial",
        True,
        (182, 231, 220),
    )
    surface.blit(footer, footer.get_rect(center=(panel.centerx, panel.bottom - 28)))


def draw_tutorial_objective_panel(
    surface: pygame.Surface,
    step: dict,
    font: pygame.font.Font,
    small_font: pygame.font.Font,
    recall_visible: bool,
) -> None:
    objective = str(step.get("objective") or "Follow the Echo Guide.")
    layout = compute_ui_layout(*surface.get_size())
    panel = (
        layout.objective_with_recall.copy()
        if recall_visible
        else layout.objective.copy()
    )
    pygame.draw.rect(surface, (7, 20, 30), panel, border_radius=10)
    pygame.draw.rect(surface, (63, 218, 196), panel, 3, border_radius=10)
    title = small_font.render("CURRENT OBJECTIVE", True, (95, 235, 210))
    surface.blit(title, (panel.x + 13, panel.y + 8))
    objective_lines = wrap_text(objective, font, panel.width - 26)[:2]
    for index, line in enumerate(objective_lines):
        image = font.render(line, True, (234, 245, 237))
        surface.blit(image, (panel.x + 13, panel.y + 32 + index * font.get_linesize()))


def get_tutorial_target_position(
    step: dict,
    npcs: list[VillageNPC],
    camera: pygame.Vector2,
    world_scale: tuple[float, float],
    surface_size: tuple[int, int],
) -> pygame.Vector2 | None:
    if step.get("target_type") == "day_end":
        return pygame.Vector2(surface_size[0] / 2, 116)
    if step.get("target_type") != "npc":
        return None
    target_key = str(step.get("target_npc_key") or "")
    target_npc = next((npc for npc in npcs if npc.key == target_key), None)
    if target_npc is None:
        return None
    scale_x, scale_y = world_scale
    return pygame.Vector2(
        (target_npc.tile_pos[0] * TILE_SIZE - camera.x) * scale_x
        + TILE_SIZE * scale_x / 2,
        (target_npc.tile_pos[1] * TILE_SIZE - camera.y) * scale_y
        + TILE_SIZE * scale_y / 2,
    )


def draw_tutorial_arrow(
    surface: pygame.Surface,
    step: dict,
    target: pygame.Vector2 | None,
    font: pygame.font.Font,
) -> None:
    if target is None:
        return
    ticks = pygame.time.get_ticks()
    pulse = (math.sin(ticks * 0.010) + 1.0) / 2.0
    color = (
        round(68 + 90 * pulse),
        round(218 + 30 * pulse),
        round(184 + 45 * pulse),
    )
    label = str(step.get("waypoint_label") or "Next objective")
    screen_w, screen_h = surface.get_size()
    layout = compute_ui_layout(screen_w, screen_h)

    if step.get("target_type") == "day_end":
        highlight = pygame.Rect(0, 0, 250, 33)
        highlight.center = (screen_w // 2, layout.hud.bottom - 24)
        pygame.draw.rect(surface, (8, 25, 35), highlight, border_radius=8)
        pygame.draw.rect(surface, color, highlight, 3, border_radius=8)
        arrow_y = highlight.y - 13 + round(pulse * 5)
        pygame.draw.polygon(
            surface,
            color,
            [
                (highlight.centerx, arrow_y + 13),
                (highlight.centerx - 13, arrow_y - 3),
                (highlight.centerx + 13, arrow_y - 3),
            ],
        )
        image = font.render("Press N — End the Day", True, (230, 252, 241))
        surface.blit(image, image.get_rect(center=highlight.center))
        return

    covered_by_right_panels = (
        target.x >= layout.memory.x - 12
        and layout.memory.y - 12 <= target.y <= layout.attitudes.bottom + 12
    )
    on_screen = (
        42 <= target.x <= screen_w - 42
        and layout.hud.bottom + 18 <= target.y <= layout.dialogue.y - 28
        and not covered_by_right_panels
    )
    if on_screen:
        ring = pygame.Rect(0, 0, 58 + round(8 * pulse), 25 + round(4 * pulse))
        ring.center = (round(target.x), round(target.y + 25))
        pygame.draw.ellipse(surface, color, ring, 3)
        bounce = round(pulse * 8)
        tip_y = round(target.y - 34 - bounce)
        pygame.draw.polygon(
            surface,
            color,
            [
                (round(target.x), tip_y + 16),
                (round(target.x - 14), tip_y - 2),
                (round(target.x + 14), tip_y - 2),
            ],
        )
        label_image = font.render(label, True, (230, 252, 241))
        label_panel = label_image.get_rect(midbottom=(round(target.x), tip_y - 8)).inflate(18, 10)
        label_panel.clamp_ip(
            pygame.Rect(8, layout.hud.bottom + 8, screen_w - 16, max(1, layout.dialogue.y - layout.hud.bottom - 16))
        )
        pygame.draw.rect(surface, (7, 22, 31), label_panel, border_radius=7)
        pygame.draw.rect(surface, color, label_panel, 2, border_radius=7)
        surface.blit(label_image, label_image.get_rect(center=label_panel.center))
        return

    center = pygame.Vector2(screen_w / 2, (layout.hud.bottom + layout.dialogue.y) / 2)
    direction = target - center
    if direction.length_squared() == 0:
        direction = pygame.Vector2(0, -1)
    direction = direction.normalize()
    scale_x = max(80, screen_w / 2 - 65) / max(abs(direction.x), 0.001)
    scale_y = max(60, (layout.dialogue.y - layout.hud.bottom) / 2 - 45) / max(abs(direction.y), 0.001)
    edge = center + direction * min(scale_x, scale_y)
    if direction.x > 0 and edge.y <= layout.attitudes.bottom + 24:
        edge.x = min(edge.x, layout.memory.x - 40)
    perpendicular = pygame.Vector2(-direction.y, direction.x)
    tip = edge + direction * 17
    base = edge - direction * 16
    pygame.draw.polygon(
        surface,
        color,
        [
            (round(tip.x), round(tip.y)),
            (round((base + perpendicular * 13).x), round((base + perpendicular * 13).y)),
            (round((base - perpendicular * 13).x), round((base - perpendicular * 13).y)),
        ],
    )
    label_image = font.render(label, True, (230, 252, 241))
    label_panel = label_image.get_rect(center=(round(edge.x), round(edge.y + 34))).inflate(16, 8)
    label_panel.clamp_ip(
        pygame.Rect(8, layout.hud.bottom + 8, screen_w - 16, max(1, layout.dialogue.y - layout.hud.bottom - 16))
    )
    pygame.draw.rect(surface, (7, 22, 31), label_panel, border_radius=7)
    pygame.draw.rect(surface, color, label_panel, 2, border_radius=7)
    surface.blit(label_image, label_image.get_rect(center=label_panel.center))


def compact_recall_summary(
    text: str,
    analysis: dict | None = None,
) -> str:
    """Turn analyzer prose into a two- or three-word UI-only label."""
    details = analysis if isinstance(analysis, dict) else {}
    tags_value = details.get("tags")
    tags = {
        str(tag).strip().casefold()
        for tag in tags_value
        if str(tag).strip()
    } if isinstance(tags_value, (list, tuple, set)) else set()
    tone = str(details.get("tone") or "").strip().casefold()
    intent = str(details.get("intent") or "").strip().casefold()

    if details.get("is_first_meeting") or details.get("memory_forbidden"):
        return "first meeting"
    if tags.intersection({"promise_broken", "trust_breach"}):
        return "broken promise"
    if "aggressive_bargain" in tags and "threat" in tags:
        return "aggressive bargain"
    # Merchant conflict without an explicit threat is the compact game label
    # for price dissatisfaction, even when the analyzer also tags bargaining.
    if "merchant_conflict" in tags and "threat" not in tags:
        return "found it pricey"
    if "aggressive_bargain" in tags:
        return "aggressive bargain"
    if tags.intersection({"rude_bargaining", "merchant_conflict"}):
        return "found it pricey"
    if "fair_trade" in tags:
        return "fair payment"
    if "purchase_interest" in tags:
        return "purchase interest"
    if tags.intersection({"possible_lie", "denial"}):
        return "evasive denial"
    if "honest_confession" in tags:
        return "honest confession"
    if "apology" in tags:
        return "apology"
    if "insult" in tags:
        return "insult"
    if "blacksmith_fairness" in tags:
        return "fair trade"
    if "guard_suspicion" in tags:
        return "suspicious denial"
    if "bribe_attempt" in tags:
        return "bribe attempt"
    if tone == "friendly":
        return "friendly meeting"
    if intent == "question":
        return "neutral question"

    cleaned = " ".join(str(text or "").split()).strip()
    normalized = cleaned.casefold()
    if "first meeting" in normalized or "no verified memory" in normalized:
        return "first meeting"
    if "no prior memory" in normalized:
        return "no prior memory"
    if "threatened petra" in normalized:
        return "threatened Petra"
    if "pressured petra" in normalized:
        return "pressured Petra"
    if "insulted gareth" in normalized:
        return "insulted Gareth"
    if "bargain" in normalized and (
        "aggress" in normalized
        or "ultimatum" in normalized
        or "threat" in normalized
    ):
        return "aggressive bargain"
    if (
        "dissatisfaction" in normalized
        or "prices" in normalized
        or ("price" in normalized and "reduction" in normalized)
    ):
        return "found it pricey"
    if "friendly" in normalized and (
        "meet" in normalized or "greet" in normalized
    ):
        return "friendly meeting"
    if "fair payment" in normalized or "paid fairly" in normalized:
        return "fair payment"
    if "deni" in normalized and "evas" in normalized:
        return "evasive denial"
    if "confess" in normalized and "honest" in normalized:
        return "honest confession"
    if "apolog" in normalized:
        return "apology"
    if "insult" in normalized:
        return "insult"
    if "bribe" in normalized:
        return "bribe attempt"

    for prefix in ("the player ", "player "):
        if normalized.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
            break
    cleaned = cleaned.rstrip(" .,!?:;")
    compact = " ".join(cleaned.split()[:3])
    return compact[:24].rstrip() or "no prior memory"


def build_recall_display_lines(trace: dict) -> list[str]:
    """Build the complete body for every Recall notification code path."""
    safe_trace = trace if isinstance(trace, dict) else {}
    is_debug = str(safe_trace.get("title") or "").casefold() == (
        "[recall debug]"
    )
    custom_lines = safe_trace.get("lines")
    if is_debug and isinstance(custom_lines, (list, tuple)):
        return [
            " ".join(str(line).split()).strip()
            for line in custom_lines
            if str(line).strip()
        ][:5]

    tags_value = safe_trace.get("tags")
    tags = (
        [str(tag).strip() for tag in tags_value if str(tag).strip()]
        if isinstance(tags_value, (list, tuple, set))
        else []
    )
    lines: list[str] = []
    promise_broken_summary = str(
        safe_trace.get("promise_broken_summary") or ""
    ).strip()
    first_or_forbidden = bool(
        safe_trace.get("is_first_meeting")
        or safe_trace.get("memory_forbidden")
    )

    if promise_broken_summary:
        lines.append("broken promise")
        lines.append(compact_recall_summary(promise_broken_summary))
    elif first_or_forbidden:
        lines.append("first meeting")
    else:
        verified_value = safe_trace.get("verified_memory")
        if isinstance(verified_value, (list, tuple)):
            memory_text = next(
                (str(item) for item in verified_value if str(item).strip()),
                "",
            )
        else:
            memory_text = str(verified_value or "").strip()
        if not memory_text:
            memory_text = str(safe_trace.get("cognee_recall") or "").strip()
        lines.append(compact_recall_summary(memory_text or "No prior memory retrieved."))

    summary_text = str(safe_trace.get("analysis_summary") or "").strip()
    if not summary_text and isinstance(custom_lines, (list, tuple)):
        summary_text = next(
            (str(line) for line in custom_lines if str(line).strip()),
            "",
        )
    if summary_text and not promise_broken_summary:
        action_analysis = dict(safe_trace)
        action_analysis["is_first_meeting"] = False
        action_analysis["memory_forbidden"] = False
        action_label = compact_recall_summary(summary_text, action_analysis)
        if action_label and action_label not in lines:
            lines.append(action_label)

    meta_parts: list[str] = []
    attitude = safe_trace.get("attitude")
    trust = safe_trace.get("trust_delta")
    hostility = safe_trace.get("hostility_level")
    if attitude is not None and str(attitude).strip():
        meta_parts.append(f"attitude: {str(attitude).strip()}")
    if trust is not None and str(trust).strip():
        meta_parts.append(f"trust: {str(trust).strip()}")
    if hostility is not None and str(hostility).strip():
        meta_parts.append(f"hostility: {str(hostility).strip()}")
    if meta_parts:
        lines.append(" | ".join(meta_parts))

    if tags:
        lines.append(f"tags: {', '.join(tags[:2])}")

    return lines[:5] or ["no prior memory"]


def draw_recall_notification(
    surface: pygame.Surface,
    trace: dict,
    title_font: pygame.font.Font | None = None,
    body_font: pygame.font.Font | None = None,
) -> None:
    """Draw a compact top-left notification without blocking dialogue."""
    safe_trace = trace if isinstance(trace, dict) else {}
    if title_font is None:
        title_font = pygame.font.Font(None, 22)
        title_font.set_bold(True)
    body_font = body_font or pygame.font.Font(None, 19)
    lines = build_recall_display_lines(safe_trace)

    panel_height = max(
        120,
        min(180, 58 + len(lines) * body_font.get_linesize()),
    )
    panel = compute_ui_layout(*surface.get_size()).recall
    panel.height = panel_height
    shadow = panel.move(5, 5)
    pygame.draw.rect(surface, (4, 8, 12), shadow)
    pygame.draw.rect(surface, (12, 18, 25), panel)
    pygame.draw.rect(surface, (222, 214, 174), panel, 3)
    pygame.draw.rect(surface, (68, 83, 83), panel.inflate(-10, -10), 1)

    title = str(safe_trace.get("title") or "[RECALL]")
    title_image = title_font.render(title, True, (247, 205, 104))
    surface.blit(title_image, (panel.x + 14, panel.y + 10))

    debug_signature = (id(trace), tuple(lines))
    if getattr(draw_recall_notification, "_debug_signature", None) != debug_signature:
        print("[recall-ui-lines]", lines)
        draw_recall_notification._debug_signature = debug_signature

    line_y = panel.y + 42
    for line in lines:
        line_image = body_font.render(line, True, (226, 232, 218))
        surface.blit(line_image, (panel.x + 14, line_y))
        line_y += body_font.get_linesize()


def arc_position(
    progress: float,
    start_x: float,
    end_x: float,
    base_y: float,
    arc_height: float,
) -> tuple[int, int]:
    progress = max(0.0, min(1.0, progress))
    x = start_x + (end_x - start_x) * progress
    y = base_y - math.sin(math.pi * progress) * arc_height
    return (round(x), round(y))


def draw_day_night_transition(
    surface: pygame.Surface,
    progress: float,
    font: pygame.font.Font,
) -> None:
    """Play one complete sunset, moon arc, and sunrise sequence."""
    progress = max(0.0, min(1.0, progress))
    if progress < 0.30:
        local_progress = progress / 0.30
        darkness = 30 + round(150 * local_progress)
        body = "sunset"
        message = "The sun sets over EchoWorld..."
    elif progress < 0.65:
        local_progress = (progress - 0.30) / 0.35
        darkness = 180
        body = "moon"
        message = (
            "Memories settle. Gossip travels."
            if local_progress < 0.68
            else "The village sleeps..."
        )
    else:
        local_progress = (progress - 0.65) / 0.35
        darkness = 180 - round(150 * local_progress)
        body = "sunrise"
        message = "A new day approaches..."

    screen_w, screen_h = surface.get_size()
    layout = compute_ui_layout(screen_w, screen_h)
    shade = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    shade.fill((8, 15, 48, darkness))
    surface.blit(shade, (0, 0))

    if darkness >= 125:
        for star_x, star_y in (
            (screen_w * 0.10, screen_h * 0.28),
            (screen_w * 0.19, screen_h * 0.41),
            (screen_w * 0.29, screen_h * 0.26),
            (screen_w * 0.72, screen_h * 0.30),
            (screen_w * 0.84, screen_h * 0.41),
            (screen_w * 0.93, screen_h * 0.26),
        ):
            pygame.draw.rect(
                surface,
                (207, 220, 224),
                (round(star_x), round(star_y), 4, 4),
            )

    if body == "sunset":
        sun_position = arc_position(
            0.5 + local_progress * 0.5,
            screen_w - 60,
            60,
            screen_h * 0.58,
            screen_h * 0.32,
        )
        pygame.draw.circle(surface, (119, 68, 35), sun_position, 39)
        pygame.draw.circle(surface, (247, 174, 61), sun_position, 33)
    elif body == "moon":
        moon_position = arc_position(
            local_progress,
            screen_w - 60,
            60,
            screen_h * 0.58,
            screen_h * 0.32,
        )
        pygame.draw.circle(surface, (204, 218, 229), moon_position, 32)
        pygame.draw.circle(
            surface,
            (31, 43, 76),
            (moon_position[0] + 13, moon_position[1] - 8),
            27,
        )
    else:
        sun_position = arc_position(
            local_progress * 0.35,
            screen_w - 60,
            60,
            screen_h * 0.58,
            screen_h * 0.32,
        )
        pygame.draw.circle(surface, (132, 73, 34), sun_position, 39)
        pygame.draw.circle(surface, (251, 193, 70), sun_position, 33)

    message_panel = pygame.Rect(0, 0, min(620, screen_w - 48), 68)
    message_panel.centerx = screen_w // 2
    message_panel.bottom = layout.dialogue.bottom
    pygame.draw.rect(surface, (14, 19, 26), message_panel)
    pygame.draw.rect(surface, (230, 210, 150), message_panel, 4)
    message_image = font.render(message, True, (247, 241, 213))
    surface.blit(message_image, message_image.get_rect(center=message_panel.center))


def draw_endday_morning_hold(
    surface: pygame.Surface,
    hold_elapsed_ms: int,
    font: pygame.font.Font,
) -> None:
    """Keep a lively morning frame visible while the backend finishes."""
    screen_w, screen_h = surface.get_size()
    layout = compute_ui_layout(screen_w, screen_h)
    morning_glow = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)
    morning_glow.fill((255, 196, 104, 34))
    surface.blit(morning_glow, (0, 0))

    sun_position = arc_position(
        0.35,
        screen_w - 60,
        60,
        screen_h * 0.58,
        screen_h * 0.32,
    )
    pygame.draw.circle(surface, (132, 73, 34), sun_position, 39)
    pygame.draw.circle(surface, (251, 193, 70), sun_position, 33)

    # Small drifting memory motes keep the hold frame alive without replaying it.
    for index in range(12):
        drift = (hold_elapsed_ms * 0.035 + index * 61) % 330
        particle_x = 60 + ((index * 97) % max(120, screen_w - 120))
        particle_y = round(screen_h * 0.72 - drift)
        particle_size = 3 if index % 3 else 5
        pygame.draw.rect(
            surface,
            (232, 214, 143),
            (particle_x, particle_y, particle_size, particle_size),
        )

    messages = (
        "Memories are settling",
        "Gossip is spreading",
        "Finalizing the new day",
    )
    message_index = (hold_elapsed_ms // 2000) % len(messages)
    dots = "." * (1 + (hold_elapsed_ms // 450) % 3)
    message = f"{messages[message_index]}{dots}"

    message_panel = pygame.Rect(0, 0, min(620, screen_w - 48), 68)
    message_panel.centerx = screen_w // 2
    message_panel.bottom = layout.dialogue.bottom
    pygame.draw.rect(surface, (14, 19, 26), message_panel)
    pygame.draw.rect(surface, (230, 210, 150), message_panel, 4)
    message_image = font.render(message, True, (247, 241, 213))
    surface.blit(message_image, message_image.get_rect(center=message_panel.center))


def draw_village_gossip_chatter(
    surface: pygame.Surface,
    chatter_lines: list[str],
    elapsed_ms: int,
    animation_progress: float,
    title_font: pygame.font.Font,
    body_font: pygame.font.Font,
) -> None:
    """Show rotating ambient speech bubbles while villagers stand together."""
    if not chatter_lines or not 0.40 <= animation_progress < 0.70:
        return

    chatter_started_ms = round(ENDDAY_ANIMATION_MS * 0.40)
    chatter_elapsed_ms = max(0, elapsed_ms - chatter_started_ms)
    bubble_duration_ms = 1200
    line_index = (chatter_elapsed_ms // bubble_duration_ms) % len(chatter_lines)
    bubble_age = chatter_elapsed_ms % bubble_duration_ms
    fade_in = min(1.0, bubble_age / 180)
    fade_out = min(1.0, (bubble_duration_ms - bubble_age) / 220)
    alpha = round(245 * min(fade_in, fade_out))
    bob = round(math.sin(chatter_elapsed_ms * 0.009) * 3)

    bubble = pygame.Surface((420, 80), pygame.SRCALPHA)
    pygame.draw.rect(bubble, (10, 17, 25, 238), bubble.get_rect())
    pygame.draw.rect(bubble, (222, 214, 174, 255), bubble.get_rect(), 3)
    pygame.draw.rect(
        bubble,
        (68, 83, 83, 255),
        bubble.get_rect().inflate(-10, -10),
        1,
    )
    heading = title_font.render("... village chatter ...", True, (247, 205, 104))
    bubble.blit(heading, (12, 8))
    text = " ".join(chatter_lines[line_index].split())
    for text_index, line in enumerate(wrap_text(text, body_font, 394)[:2]):
        image = body_font.render(line, True, (226, 232, 218))
        bubble.blit(image, (12, 36 + text_index * body_font.get_linesize()))
    bubble.set_alpha(alpha)
    screen_w, screen_h = surface.get_size()
    bubble_x = (screen_w - bubble.get_width()) // 2
    bubble_y = max(140, round(screen_h * 0.24)) + bob
    surface.blit(bubble, (bubble_x, bubble_y))

    # Two tiny ellipsis bubbles suggest several overlapping conversations
    # without covering the gathered sprites with more text.
    for center in (
        (screen_w // 2 - 74, round(screen_h * 0.47)),
        (screen_w // 2 + 74, round(screen_h * 0.51)),
    ):
        pygame.draw.circle(surface, (12, 18, 25), center, 17)
        pygame.draw.circle(surface, (201, 192, 151), center, 17, 2)
        for dot_offset in (-7, 0, 7):
            pygame.draw.rect(
                surface,
                (232, 214, 143),
                (center[0] + dot_offset - 2, center[1] - 2, 4, 4),
            )


async def run_game(browser_mode: bool = False) -> None:
    global DIALOGUE_TEXT_WIDTH
    print(f"[game] run_game started browser_mode={browser_mode}")
    pygame.init()
    pygame.display.set_caption("EchoWorld - Pixel Village")
    display_size = get_display_size(browser_mode)
    display_flags = pygame.RESIZABLE if browser_mode else 0
    window = pygame.display.set_mode(display_size, display_flags)
    render_metrics = compute_render_metrics(*display_size, browser_mode)
    internal_surface = pygame.Surface(
        (render_metrics.internal_w, render_metrics.internal_h)
    )
    ui_layout = compute_ui_layout(*display_size)
    DIALOGUE_TEXT_WIDTH = max(280, ui_layout.dialogue.width - 48)
    clock = pygame.time.Clock()

    ui_fonts = create_ui_fonts(*display_size)
    hud_title_font = ui_fonts["hud_title"]
    ui_font = ui_fonts["ui"]
    helper_font = ui_fonts["helper"]
    dialogue_font = ui_fonts["dialogue"]
    menu_font = ui_fonts["menu"]
    title_screen_font = ui_fonts["title_screen"]
    attitude_icon_font = ui_fonts["attitude_icon"]
    recall_title_font = ui_fonts["recall_title"]
    recall_body_font = ui_fonts["recall_body"]
    gossip_title_font = ui_fonts["gossip_title"]
    gossip_body_font = ui_fonts["gossip_body"]
    tutorial_title_font = ui_fonts["tutorial_title"]
    tutorial_body_font = ui_fonts["tutorial_body"]
    tutorial_small_font = ui_fonts["tutorial_small"]

    tile_map = create_village_map()
    buildings = create_buildings()
    npcs = create_npcs()
    tile_assets = {
        "grass": make_grass_tile(TILE_SIZE),
        "path": make_path_tile(TILE_SIZE),
        "tree": make_tree_tile(TILE_SIZE),
    }
    roof_tiles = {
        building.roof_color: make_roof_tile(TILE_SIZE, building.roof_color)
        for building in buildings
    }
    wall_tile = make_wall_tile(TILE_SIZE)
    player_sprites = create_player_sprites()
    alert_bubble = make_exclamation_bubble(TILE_SIZE)
    blocked_tiles = build_blocked_tiles(tile_map, buildings, npcs)

    start_tile = (14, 10)
    player = Player(
        tile_pos=start_tile,
        pixel_pos=pygame.Vector2(start_tile[0] * TILE_SIZE, start_tile[1] * TILE_SIZE),
        target_tile=start_tile,
    )

    menu_open = False
    selected_option = 0
    menu_npc: VillageNPC | None = None
    dialogue_title: str | None = None
    dialogue_pages: list[str] = []
    dialogue_page_index = 0
    dialogue_history: list[tuple[str, str]] = []
    input_active = False
    input_npc: VillageNPC | None = None
    input_action = "talk"
    input_text = ""
    input_error = ""
    backend_adapter: BackendAdapter = create_backend_adapter(browser_mode)
    print(f"[game] using {backend_adapter.__class__.__name__}")
    backend_job: BackendJob | None = None
    talk_future: asyncio.Task | None = None
    talk_pending_npc: VillageNPC | None = None
    talk_pending_player_message: str | None = None
    talk_pending_was_forgotten = False
    talk_pending_is_first_meeting = False
    talk_pending_memory_forbidden = False
    talk_pending_attitude = "neutral"
    talk_pending_action = "talk"
    talk_pending_forced_callout = ""
    talk_mode = "playing"
    recall_notification: dict | None = None
    recall_notification_started_at = 0
    recall_notification_bound_to_dialogue = False
    day = 1
    run_id = f"echoworld_run_{uuid4().hex[:8]}"
    current_day_session_id = f"{run_id}_day_{day}"
    last_api_event = "No Cognee API used yet."
    gossip_unlocked = False
    gossip_source_session_id: str | None = None
    met_npcs: set[str] = set()
    forgotten_npcs: set[str] = set()
    npc_memory_cutoffs: dict[str, int] = {}
    npc_attitudes = {key: "neutral" for key in ATTITUDE_NAMES}
    promise_state: dict[str, Any] = default_promise_state()
    event_cache: list[dict[str, Any]] = []
    village_attitude_summary = attitude_summary_from_state(npc_attitudes)
    title_screen_active = True
    reset_confirmation = False
    endday_active = False
    endday_started_at = 0
    endday_future: asyncio.Task | None = None
    endday_source_session_id: str | None = None
    endday_chatter_lines: list[str] = []
    tutorial_state = load_tutorial_state()
    tutorial_pending_step_id: str | None = None
    tutorial_popup_deferred = False
    running = True

    # Draw before awaiting the server so a cold-starting hosted backend never
    # looks like an empty browser tab.
    draw_title_screen(window, title_screen_font, ui_font, ui_font)
    pygame.display.flip()
    try:
        promise_result, attitude_result, events_result = await asyncio.gather(
            backend_adapter.get_promises(),
            backend_adapter.get_attitudes(),
            backend_adapter.get_events(),
        )
        loaded_promises = promise_result.get("promises")
        if isinstance(loaded_promises, dict):
            promise_state = loaded_promises
        loaded_attitudes = attitude_result.get("attitudes")
        if isinstance(loaded_attitudes, dict):
            npc_attitudes.update(
                {key: str(value) for key, value in loaded_attitudes.items() if key in npc_attitudes}
            )
        loaded_events = events_result.get("events")
        if isinstance(loaded_events, list):
            event_cache = [event for event in loaded_events if isinstance(event, dict)]
        village_attitude_summary = attitude_summary_from_state(npc_attitudes)
    except Exception as exc:
        last_api_event = f"Backend connection pending: {exc}"

    while running:
        delta_seconds = min(clock.tick(FPS) / 1000.0, 0.05)
        if browser_mode:
            requested_size = get_display_size(True)
            if requested_size != window.get_size():
                window = pygame.display.set_mode(requested_size, pygame.RESIZABLE)
                render_metrics = compute_render_metrics(*requested_size, True)
                internal_surface = pygame.Surface(
                    (render_metrics.internal_w, render_metrics.internal_h)
                )
                ui_layout = compute_ui_layout(*requested_size)
                DIALOGUE_TEXT_WIDTH = max(280, ui_layout.dialogue.width - 48)
                ui_fonts = create_ui_fonts(*requested_size)
                hud_title_font = ui_fonts["hud_title"]
                ui_font = ui_fonts["ui"]
                helper_font = ui_fonts["helper"]
                dialogue_font = ui_fonts["dialogue"]
                menu_font = ui_fonts["menu"]
                title_screen_font = ui_fonts["title_screen"]
                attitude_icon_font = ui_fonts["attitude_icon"]
                recall_title_font = ui_fonts["recall_title"]
                recall_body_font = ui_fonts["recall_body"]
                gossip_title_font = ui_fonts["gossip_title"]
                gossip_body_font = ui_fonts["gossip_body"]
                tutorial_title_font = ui_fonts["tutorial_title"]
                tutorial_body_font = ui_fonts["tutorial_body"]
                tutorial_small_font = ui_fonts["tutorial_small"]
                print(
                    "[game] browser resize "
                    f"screen={requested_size} internal="
                    f"{render_metrics.internal_w}x{render_metrics.internal_h} "
                    f"scale={render_metrics.pixel_scale}"
                )
        nearby_npc = None if player.moving else get_nearby_npc(player.tile_pos, npcs)
        if (
            recall_notification is not None
            and pygame.time.get_ticks() - recall_notification_started_at
            >= RECALL_NOTIFICATION_MS
        ):
            recall_notification = None
            recall_notification_started_at = 0
            recall_notification_bound_to_dialogue = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue

            if event.type == pygame.VIDEORESIZE and browser_mode:
                # Browser resize events can lag behind the canvas, so re-read
                # the live viewport instead of trusting a stale event size.
                resized = get_display_size(True)
                window = pygame.display.set_mode(resized, pygame.RESIZABLE)
                render_metrics = compute_render_metrics(*resized, True)
                internal_surface = pygame.Surface(
                    (render_metrics.internal_w, render_metrics.internal_h)
                )
                ui_layout = compute_ui_layout(*resized)
                DIALOGUE_TEXT_WIDTH = max(280, ui_layout.dialogue.width - 48)
                ui_fonts = create_ui_fonts(*resized)
                hud_title_font = ui_fonts["hud_title"]
                ui_font = ui_fonts["ui"]
                helper_font = ui_fonts["helper"]
                dialogue_font = ui_fonts["dialogue"]
                menu_font = ui_fonts["menu"]
                title_screen_font = ui_fonts["title_screen"]
                attitude_icon_font = ui_fonts["attitude_icon"]
                recall_title_font = ui_fonts["recall_title"]
                recall_body_font = ui_fonts["recall_body"]
                gossip_title_font = ui_fonts["gossip_title"]
                gossip_body_font = ui_fonts["gossip_body"]
                tutorial_title_font = ui_fonts["tutorial_title"]
                tutorial_body_font = ui_fonts["tutorial_body"]
                tutorial_small_font = ui_fonts["tutorial_small"]
                continue

            if (
                event.type == pygame.KEYDOWN
                and event.key == pygame.K_F11
                and not browser_mode
            ):
                pygame.display.toggle_fullscreen()
                continue

            if event.type == pygame.KEYDOWN and event.key == pygame.K_F8:
                recall_notification = {
                    "title": "[RECALL DEBUG]",
                    "lines": [
                        "If you can see this, notification rendering works.",
                        "This notification remains visible for five seconds.",
                    ],
                }
                recall_notification_started_at = pygame.time.get_ticks()
                recall_notification_bound_to_dialogue = False
                continue

            if title_screen_active:
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        title_screen_active = False
                    elif event.key == pygame.K_ESCAPE:
                        running = False
                continue

            if (
                tutorial_is_active(tutorial_state)
                and tutorial_state.get("popup_open")
                and not tutorial_popup_deferred
            ):
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_s:
                        tutorial_state = skip_tutorial()
                        tutorial_pending_step_id = None
                    elif event.key in (
                        pygame.K_RETURN,
                        pygame.K_KP_ENTER,
                        pygame.K_SPACE,
                        pygame.K_e,
                    ):
                        tutorial_state = advance_tutorial_popup(tutorial_state)
                continue

            if endday_active:
                # End Day cannot be cancelled once memory consolidation begins.
                continue

            if input_active:
                if event.type == pygame.TEXTINPUT:
                    printable_text = "".join(
                        character
                        for character in event.text
                        if character.isprintable()
                    )
                    remaining = MAX_PLAYER_INPUT - len(input_text)
                    input_text += printable_text[:remaining]
                    input_error = ""
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        pygame.key.stop_text_input()
                        input_active = False
                        talk_mode = "playing"
                        input_npc = None
                        input_action = "talk"
                        input_text = ""
                        input_error = ""
                    elif event.key == pygame.K_BACKSPACE:
                        input_text = input_text[:-1]
                        input_error = ""
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        raw_player_message = input_text.strip()
                        if not raw_player_message:
                            input_error = (
                                "Type a confession before submitting."
                                if input_action == "confess"
                                else "Type a message before submitting."
                            )
                        elif input_npc is not None:
                            is_confession = input_action == "confess"
                            player_message = (
                                format_confession_message(raw_player_message)
                                if is_confession
                                else raw_player_message
                            )
                            history_speaker = (
                                "You confessed" if is_confession else "You"
                            )
                            dialogue_history.append((history_speaker, player_message))
                            is_first_meeting = input_npc.key not in met_npcs
                            was_forgotten = input_npc.key in forgotten_npcs
                            verified_memory = get_verified_npc_memory(
                                input_npc.key,
                                run_id,
                                forgotten_npcs,
                                met_npcs,
                                npc_memory_cutoffs,
                                event_cache,
                            )
                            memory_forbidden = (
                                is_first_meeting
                                or was_forgotten
                                or (
                                    not verified_memory
                                    and player_asks_about_memory(player_message)
                                )
                            )
                            current_attitude = npc_attitudes.get(
                                input_npc.key,
                                "neutral",
                            )
                            promise_context = promise_context_for_npc(
                                input_npc.key,
                                promise_state,
                            )
                            forced_callout = (
                                pending_mira_callout(promise_state)
                                if input_npc.key == "guard"
                                else ""
                            )
                            talk_payload = {
                                "npc_key": input_npc.key,
                                "message": player_message,
                                "session_id": current_day_session_id,
                                "day": day,
                                "allow_hearsay": gossip_unlocked,
                                "is_first_meeting": is_first_meeting,
                                "verified_memory": verified_memory,
                                "memory_forbidden": memory_forbidden,
                                "attitude": current_attitude,
                                "hearsay_session_id": gossip_source_session_id,
                                "promise_context": promise_context,
                                "forced_callout": forced_callout,
                            }
                            talk_future = asyncio.create_task(
                                backend_adapter.talk(talk_payload)
                            )
                            talk_pending_npc = input_npc
                            talk_pending_player_message = player_message
                            talk_pending_was_forgotten = was_forgotten
                            talk_pending_is_first_meeting = is_first_meeting
                            talk_pending_memory_forbidden = memory_forbidden
                            talk_pending_attitude = current_attitude
                            talk_pending_action = input_action
                            talk_pending_forced_callout = forced_callout
                            talk_mode = "talk_loading"
                            last_api_event = (
                                "confess + remember()"
                                if is_confession
                                else "recalling memory"
                            )
                            pygame.key.stop_text_input()
                            input_active = False
                            input_npc = None
                            input_action = "talk"
                            input_text = ""
                            input_error = ""
                continue

            if event.type != pygame.KEYDOWN:
                continue

            if backend_job is not None:
                continue

            if talk_future is not None:
                continue

            if reset_confirmation:
                if event.key == pygame.K_y:
                    dialogue_history.clear()
                    day = 1
                    run_id = f"echoworld_run_{uuid4().hex[:8]}"
                    current_day_session_id = f"{run_id}_day_{day}"
                    last_api_event = "No Cognee API used yet."
                    gossip_unlocked = False
                    gossip_source_session_id = None
                    endday_chatter_lines = []
                    met_npcs.clear()
                    forgotten_npcs.clear()
                    npc_memory_cutoffs.clear()
                    player.tile_pos = start_tile
                    player.pixel_pos = pygame.Vector2(
                        start_tile[0] * TILE_SIZE,
                        start_tile[1] * TILE_SIZE,
                    )
                    player.target_tile = start_tile
                    player.moving = False
                    player.facing = "down"
                    menu_open = False
                    menu_npc = None
                    input_active = False
                    input_npc = None
                    input_action = "talk"
                    input_text = ""
                    input_error = ""
                    talk_future = None
                    talk_pending_npc = None
                    talk_pending_player_message = None
                    talk_pending_was_forgotten = False
                    talk_pending_is_first_meeting = False
                    talk_pending_memory_forbidden = False
                    talk_pending_attitude = "neutral"
                    talk_pending_action = "talk"
                    talk_pending_forced_callout = ""
                    talk_mode = "playing"
                    recall_notification = None
                    recall_notification_started_at = 0
                    recall_notification_bound_to_dialogue = False
                    event_cache.clear()
                    promise_state = default_promise_state()
                    npc_attitudes = {key: "neutral" for key in ATTITUDE_NAMES}
                    tutorial_state = reset_tutorial()
                    tutorial_pending_step_id = None
                    tutorial_popup_deferred = True
                    village_attitude_summary = attitude_summary_from_state(
                        npc_attitudes
                    )
                    dialogue_title = None
                    dialogue_pages = []
                    dialogue_page_index = 0
                    backend_job = start_backend_job(
                        "reset",
                        backend_adapter.reset(),
                    )
                    reset_confirmation = False
                elif event.key in (pygame.K_n, pygame.K_ESCAPE):
                    reset_confirmation = False
                continue

            if dialogue_pages:
                if event.key == pygame.K_ESCAPE:
                    dialogue_title = None
                    dialogue_pages = []
                    dialogue_page_index = 0
                    if talk_mode == "dialogue":
                        talk_mode = "playing"
                elif event.key in (
                    pygame.K_SPACE,
                    pygame.K_e,
                    pygame.K_RETURN,
                    pygame.K_KP_ENTER,
                ):
                    if dialogue_page_index + 1 < len(dialogue_pages):
                        dialogue_page_index += 1
                    else:
                        dialogue_title = None
                        dialogue_pages = []
                        dialogue_page_index = 0
                        if talk_mode == "dialogue":
                            talk_mode = "playing"
                continue

            if menu_open:
                active_menu_options = get_menu_options_for_npc(
                    menu_npc,
                    tutorial_state,
                    promise_state,
                )
                selected_option %= len(active_menu_options)
                if event.key in (pygame.K_UP, pygame.K_w):
                    selected_option = (selected_option - 1) % len(
                        active_menu_options
                    )
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    selected_option = (selected_option + 1) % len(
                        active_menu_options
                    )
                elif event.key == pygame.K_ESCAPE:
                    menu_open = False
                    menu_npc = None
                    talk_mode = "playing"
                elif event.key in (pygame.K_e, pygame.K_RETURN, pygame.K_KP_ENTER):
                    action = active_menu_options[selected_option]
                    selected_npc = menu_npc
                    if action == "Cancel":
                        menu_open = False
                        menu_npc = None
                        talk_mode = "playing"
                    elif selected_npc is not None and action == "Talk":
                        menu_open = False
                        menu_npc = None
                        input_active = True
                        input_npc = selected_npc
                        input_action = "talk"
                        input_text = ""
                        input_error = ""
                        talk_mode = "input"
                        pygame.key.start_text_input()
                    elif selected_npc is not None and action == "Confess":
                        menu_open = False
                        menu_npc = None
                        input_active = True
                        input_npc = selected_npc
                        input_action = "confess"
                        input_text = ""
                        input_error = ""
                        talk_mode = "input"
                        pygame.key.start_text_input()
                    elif (
                        selected_npc is not None
                        and selected_npc.key == "guard"
                        and action == "Promise No Trouble"
                    ):
                        menu_open = False
                        menu_npc = None
                        talk_mode = "playing"
                        backend_job = start_backend_job(
                            "promise",
                            backend_adapter.make_promise(
                                day,
                                current_day_session_id,
                            ),
                            npc=selected_npc,
                        )
                        last_api_event = "remembering promise..."
                    elif selected_npc is not None and action == "Bribe / Forget":
                        menu_open = False
                        menu_npc = None
                        talk_mode = "playing"
                        backend_job = start_backend_job(
                            "bribe",
                            backend_adapter.bribe(selected_npc.key),
                            npc=selected_npc,
                        )
                        last_api_event = (
                            f"Attempting forget() for {selected_npc.display_name}..."
                        )
                    elif selected_npc is not None and action == "Memory":
                        menu_open = False
                        menu_npc = None
                        talk_mode = "playing"
                        try:
                            memory_text = build_local_memory_text(
                                selected_npc,
                                event_cache,
                                allow_hearsay=gossip_unlocked,
                                hearsay_session_id=gossip_source_session_id,
                            )
                        except Exception as exc:
                            memory_text = f"Local memory display failed: {exc}"
                            dialogue_title = "System"
                            last_api_event = "Fast local debug memory failed."
                        else:
                            dialogue_title = selected_npc.display_name
                            last_api_event = "Fast local debug memory shown."
                        dialogue_pages = paginate_dialogue(
                            memory_text,
                            dialogue_font,
                        )
                        dialogue_page_index = 0
                        dialogue_history.append(
                            (dialogue_title or "System", memory_text)
                        )
                continue

            if event.key in (pygame.K_e, pygame.K_RETURN, pygame.K_KP_ENTER):
                if nearby_npc is not None:
                    tutorial_step = get_current_tutorial_step(tutorial_state)
                    if (
                        tutorial_is_active(tutorial_state)
                        and tutorial_step is not None
                        and (
                            tutorial_step.get("target_type") != "npc"
                            or tutorial_step.get("target_npc_key")
                            != nearby_npc.key
                        )
                    ):
                        continue
                    menu_open = True
                    menu_npc = nearby_npc
                    selected_option = 0
                    talk_mode = "menu"
            elif event.key == pygame.K_n and not player.moving:
                tutorial_step = get_current_tutorial_step(tutorial_state)
                if (
                    tutorial_is_active(tutorial_state)
                    and tutorial_step is not None
                    and tutorial_step.get("expected_action") != "end_day"
                ):
                    continue
                # End Day owns a non-blocking loop future; animation runs separately.
                endday_chatter_lines = build_gossip_chatter_lines(
                    run_id,
                    event_cache,
                )
                endday_source_session_id = current_day_session_id
                endday_future = asyncio.create_task(
                    backend_adapter.endday(endday_source_session_id, run_id)
                )
                endday_active = True
                endday_started_at = pygame.time.get_ticks()
                last_api_event = "improve() + gossip"
            elif event.key == pygame.K_r and not player.moving:
                reset_confirmation = True

        if not running:
            break

        if title_screen_active:
            draw_title_screen(
                window,
                title_screen_font,
                ui_font,
                ui_font,
            )
            if recall_notification is not None:
                draw_recall_notification(
                    window,
                    recall_notification,
                    recall_title_font,
                    recall_body_font,
                )
            pygame.display.flip()
            await asyncio.sleep(0)
            continue

        if endday_active and endday_future is not None:
            elapsed_ms = pygame.time.get_ticks() - endday_started_at
            animation_progress = min(
                elapsed_ms / ENDDAY_ANIMATION_MS,
                1.0,
            )
            if animation_progress >= 1.0 and endday_future.done():
                try:
                    endday_result = endday_future.result()
                except Exception as exc:
                    error_text = f"End Day failed: {exc}"
                    dialogue_title = "System"
                    dialogue_pages = paginate_dialogue(error_text, dialogue_font)
                    dialogue_page_index = 0
                    dialogue_history.append(("System", error_text))
                    last_api_event = error_text
                else:
                    attitude_report = endday_result.get("attitude_report") or []
                    updated_attitudes = endday_result.get("attitudes")
                    if isinstance(updated_attitudes, dict):
                        npc_attitudes.update(
                            {
                                key: str(value)
                                for key, value in updated_attitudes.items()
                                if key in npc_attitudes
                            }
                        )
                    village_attitude_summary = attitude_summary_from_state(
                        npc_attitudes
                    )
                    gossip_unlocked = True
                    gossip_source_session_id = endday_source_session_id
                    day += 1
                    current_day_session_id = f"{run_id}_day_{day}"
                    result_text = (
                        "Night Report:\n"
                        + "\n".join(attitude_report)
                        + "\n\nA new day begins. NPC memories were consolidated "
                        "and gossip spread. NPC attitudes now affect dialogue "
                        "tone."
                    )
                    dialogue_title = "System"
                    dialogue_pages = paginate_dialogue(result_text, dialogue_font)
                    dialogue_page_index = 0
                    dialogue_history.append(("System", result_text))
                    last_api_event = "improve() -> attitude update"
                    if action_completes_current_step(
                        tutorial_state,
                        "end_day",
                        mira_promise(promise_state),
                    ):
                        current_tutorial_step = get_current_tutorial_step(
                            tutorial_state
                        )
                        if current_tutorial_step is not None:
                            tutorial_state = complete_tutorial_step(
                                tutorial_state,
                                str(current_tutorial_step.get("id")),
                            )
                            # The End Day objective is complete now. Keep the
                            # success popup deferred only until the Night Report
                            # dialogue is dismissed, so "Press N" cannot linger.
                            tutorial_popup_deferred = True
                            tutorial_pending_step_id = None
                endday_active = False
                endday_future = None
                endday_source_session_id = None

        if talk_future is not None and talk_future.done():
            completed_talk_future = talk_future
            completed_talk_npc = talk_pending_npc
            completed_talk_action = talk_pending_action
            completed_player_message = talk_pending_player_message or ""
            completed_forced_callout = talk_pending_forced_callout
            talk_future = None
            try:
                talk_result = completed_talk_future.result()
                if isinstance(talk_result, dict):
                    talk_metadata = talk_result
                    reply = str(talk_result.get("reply") or "").strip()
                    trace_value = talk_result.get("recall_trace")
                    recall_trace = (
                        dict(trace_value)
                        if isinstance(trace_value, dict)
                        else {}
                    )
                else:
                    talk_metadata = {}
                    reply = str(talk_result).strip()
                    recall_trace = {}
                if not reply:
                    raise RuntimeError("NPC returned an empty reply.")
            except Exception as exc:
                action_label = (
                    "Confession" if completed_talk_action == "confess" else "Talk"
                )
                error_text = f"{action_label} failed: {exc}"
                dialogue_title = "System"
                dialogue_pages = paginate_dialogue(error_text, dialogue_font)
                dialogue_page_index = 0
                dialogue_history.append(("System", error_text))
                last_api_event = error_text
                talk_mode = "dialogue"
            else:
                if not recall_trace:
                    recall_trace = {
                        "title": "[RECALL]",
                        "lines": [
                            "No prior memory retrieved.",
                            "This fallback proves the recall overlay state is active.",
                        ],
                    }
                recall_trace.setdefault("cognee_recall", "")
                recall_trace.setdefault(
                    "verified_memory",
                    "No prior memory retrieved.",
                )
                recall_trace.setdefault("attitude", talk_pending_attitude)
                recall_trace.setdefault("tags", [])
                recall_trace.setdefault(
                    "is_first_meeting",
                    talk_pending_is_first_meeting,
                )
                recall_trace.setdefault(
                    "memory_forbidden",
                    talk_pending_memory_forbidden,
                )

                analysis_value = talk_metadata.get("analysis") or recall_trace.get(
                    "analysis"
                )
                if isinstance(analysis_value, dict):
                    completed_analysis = dict(analysis_value)
                else:
                    completed_analysis = {
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
                    }

                updated_promises = talk_metadata.get("promises")
                if isinstance(updated_promises, dict):
                    promise_state = updated_promises
                promise_broken_now = bool(
                    talk_metadata.get("promise_broken_now", False)
                )

                if completed_talk_npc is not None:
                    event_cache.append(
                        {
                            "session_id": current_day_session_id,
                            "npc_key": completed_talk_npc.key,
                            "npc_name": completed_talk_npc.display_name,
                            "summary": str(completed_analysis.get("summary") or ""),
                            "analysis": completed_analysis,
                        }
                    )

                recall_notification = recall_trace
                recall_notification_started_at = pygame.time.get_ticks()
                recall_notification_bound_to_dialogue = True
                dialogue_title = (
                    completed_talk_npc.display_name
                    if completed_talk_npc is not None
                    else "NPC"
                )
                dialogue_pages = paginate_dialogue(reply, dialogue_font)
                dialogue_page_index = 0
                dialogue_history.append((dialogue_title, reply))
                talk_mode = "dialogue"
                last_api_event = (
                    "confess + remember()"
                    if completed_talk_action == "confess"
                    else (
                        "recall() retrieved NPC memory; remember() stored the new "
                        "interaction."
                    )
                )
                if promise_broken_now:
                    last_api_event = "promise broken"

                if completed_talk_npc is not None:
                    met_npcs.add(completed_talk_npc.key)
                    if talk_pending_was_forgotten:
                        forgotten_npcs.discard(completed_talk_npc.key)
                    if interaction_completes_current_step(
                        tutorial_state,
                        completed_talk_npc.key,
                        completed_talk_action,
                        completed_analysis,
                        completed_player_message,
                        day,
                        mira_promise(promise_state),
                    ):
                        current_tutorial_step = get_current_tutorial_step(
                            tutorial_state
                        )
                        if current_tutorial_step is not None:
                            tutorial_pending_step_id = str(
                                current_tutorial_step.get("id")
                            )

            talk_pending_npc = None
            talk_pending_player_message = None
            talk_pending_was_forgotten = False
            talk_pending_is_first_meeting = False
            talk_pending_memory_forbidden = False
            talk_pending_attitude = "neutral"
            talk_pending_action = "talk"
            talk_pending_forced_callout = ""

        if backend_job is not None and backend_job.future.done():
            completed_job = backend_job
            backend_job = None
            try:
                backend_result = completed_job.future.result()
            except Exception as exc:
                error_text = f"{completed_job.action.replace('_', ' ').title()} failed: {exc}"
                dialogue_title = "System"
                dialogue_pages = paginate_dialogue(error_text, dialogue_font)
                dialogue_page_index = 0
                dialogue_history.append(("System", error_text))
                last_api_event = error_text
            else:
                if completed_job.action == "bribe":
                    result_text = str(
                        backend_result.get("message")
                        if isinstance(backend_result, dict)
                        else backend_result
                    )
                    dialogue_title = "System"
                    dialogue_pages = paginate_dialogue(result_text, dialogue_font)
                    dialogue_history.append(("System", result_text))
                    last_api_event = (
                        "forget() was attempted; if Cloud deletion failed, dataset "
                        "rotation isolated a fresh NPC memory."
                    )
                    if completed_job.npc is not None:
                        forgotten_npcs.add(completed_job.npc.key)
                        met_npcs.discard(completed_job.npc.key)
                        npc_memory_cutoffs[completed_job.npc.key] = len(event_cache)
                    if isinstance(backend_result, dict):
                        updated_attitudes = backend_result.get("attitudes")
                        if isinstance(updated_attitudes, dict):
                            npc_attitudes.update(updated_attitudes)
                        updated_promises = backend_result.get("promises")
                        if isinstance(updated_promises, dict):
                            promise_state = updated_promises
                    village_attitude_summary = attitude_summary_from_state(
                        npc_attitudes
                    )
                elif completed_job.action == "promise":
                    result_data = backend_result if isinstance(backend_result, dict) else {}
                    result_text = str(
                        result_data.get("message")
                        or "Then keep your word. No trouble in my village."
                    )
                    updated_promises = result_data.get("promises")
                    if isinstance(updated_promises, dict):
                        promise_state = updated_promises
                    dialogue_title = (
                        completed_job.npc.display_name
                        if completed_job.npc is not None
                        else "Captain Mira the Guard"
                    )
                    dialogue_pages = paginate_dialogue(result_text, dialogue_font)
                    dialogue_history.append((dialogue_title, result_text))
                    talk_mode = "dialogue"
                    last_api_event = "promise remembered"
                    met_npcs.add("guard")
                    event_cache.append(
                        {
                            "session_id": current_day_session_id,
                            "npc_key": "guard",
                            "npc_name": "Captain Mira the Guard",
                            "summary": "Player promised Captain Mira not to cause trouble.",
                            "analysis": {
                                "intent": "promise",
                                "tone": "respectful",
                                "tags": ["promise_made", "no_trouble_promise"],
                                "trust_delta": 1,
                                "summary": "Player promised Captain Mira not to cause trouble.",
                            },
                        }
                    )
                    if action_completes_current_step(
                        tutorial_state,
                        "promise",
                        mira_promise(promise_state),
                    ):
                        current_tutorial_step = get_current_tutorial_step(
                            tutorial_state
                        )
                        if current_tutorial_step is not None:
                            tutorial_pending_step_id = str(
                                current_tutorial_step.get("id")
                            )
                elif completed_job.action == "reset":
                    result_data = backend_result if isinstance(backend_result, dict) else {}
                    result_text = str(
                        result_data.get("message")
                        or "Demo state reset. For a full memory wipe, use bribe on individual NPCs."
                    )
                    updated_attitudes = result_data.get("attitudes")
                    if isinstance(updated_attitudes, dict):
                        npc_attitudes.update(updated_attitudes)
                    updated_promises = result_data.get("promises")
                    if isinstance(updated_promises, dict):
                        promise_state = updated_promises
                    village_attitude_summary = attitude_summary_from_state(
                        npc_attitudes
                    )
                    dialogue_history.append(("System", result_text))
                    # Reset returns to the landing screen. Pressing Enter then
                    # reveals the freshly reset intro popup; a normal launch
                    # keeps whatever tutorial progress was loaded above.
                    dialogue_title = None
                    dialogue_pages = []
                    title_screen_active = True
                    tutorial_popup_deferred = False
                dialogue_page_index = 0

        if tutorial_popup_deferred and not dialogue_pages:
            tutorial_popup_deferred = False

        if (
            tutorial_pending_step_id is not None
            and not dialogue_pages
            and talk_mode not in {"talk_loading", "input", "menu"}
            and talk_future is None
            and backend_job is None
            and not endday_active
        ):
            tutorial_state = complete_tutorial_step(
                tutorial_state,
                tutorial_pending_step_id,
            )
            tutorial_pending_step_id = None

        # Talk/Confess recall cards share the lifecycle of their dialogue. This
        # state invariant catches every dismissal path without depending on a
        # particular key branch.
        if recall_notification_bound_to_dialogue:
            dialogue_is_open = bool(dialogue_pages) and talk_mode == "dialogue"
            if not dialogue_is_open:
                recall_notification = None
                recall_notification_started_at = 0
                recall_notification_bound_to_dialogue = False

        interface_busy = (
            menu_open
            or input_active
            or backend_job is not None
            or talk_future is not None
            or talk_mode == "talk_loading"
            or bool(dialogue_pages)
            or reset_confirmation
            or endday_active
            or (
                tutorial_is_active(tutorial_state)
                and bool(tutorial_state.get("popup_open"))
                and not tutorial_popup_deferred
            )
        )
        if not interface_busy:
            if not player.moving:
                direction = held_direction(pygame.key.get_pressed())
                if direction is not None:
                    try_start_player_move(player, direction, blocked_tiles)
            update_player(player, delta_seconds)

        nearby_npc = None if player.moving else get_nearby_npc(player.tile_pos, npcs)
        endday_elapsed_ms = 0
        endday_animation_progress = 0.0
        endday_npc_positions: dict[str, pygame.Vector2] | None = None
        if endday_active and endday_future is not None:
            endday_elapsed_ms = pygame.time.get_ticks() - endday_started_at
            endday_animation_progress = min(
                endday_elapsed_ms / ENDDAY_ANIMATION_MS,
                1.0,
            )
            endday_npc_positions = get_endday_npc_positions(
                npcs,
                endday_animation_progress,
                endday_elapsed_ms,
            )
        camera = draw_world(
            internal_surface,
            tile_map,
            buildings,
            npcs,
            player,
            player_sprites,
            tile_assets,
            roof_tiles,
            wall_tile,
            alert_bubble,
            None if endday_active else nearby_npc,
            npc_positions=endday_npc_positions,
            show_player=not endday_active,
        )
        # pygame.transform.scale is nearest-neighbor, preserving hard pixel edges.
        screen_size = window.get_size()
        world_scale = (
            screen_size[0] / internal_surface.get_width(),
            screen_size[1] / internal_surface.get_height(),
        )
        scaled_frame = pygame.transform.scale(internal_surface, screen_size)
        window.fill((5, 8, 13))
        window.blit(scaled_frame, (0, 0))
        if not endday_active:
            draw_npc_attitude_icons(
                window,
                npcs,
                camera,
                npc_attitudes,
                attitude_icon_font,
                world_scale,
            )

        if endday_active and endday_future is not None:
            if endday_animation_progress < 1.0:
                draw_day_night_transition(
                    window,
                    endday_animation_progress,
                    ui_font,
                )
            else:
                draw_endday_morning_hold(
                    window,
                    endday_elapsed_ms - ENDDAY_ANIMATION_MS,
                    ui_font,
                )

        # UI is drawn after scaling so type stays sharp at the final resolution.
        draw_hud(
            window,
            None if endday_active else nearby_npc,
            npc_attitudes,
            day,
            last_api_event,
            hud_title_font,
            ui_font,
            helper_font,
        )
        draw_village_attitude_panel(
            window,
            village_attitude_summary,
            helper_font,
        )
        if endday_active and endday_future is not None:
            draw_village_gossip_chatter(
                window,
                endday_chatter_lines,
                endday_elapsed_ms,
                endday_animation_progress,
                gossip_title_font,
                gossip_body_font,
            )
        current_tutorial_step = get_current_tutorial_step(tutorial_state)
        tutorial_guidance_visible = bool(
            current_tutorial_step is not None
            and tutorial_is_active(tutorial_state)
            and not tutorial_state.get("popup_open")
            and not endday_active
        )
        if tutorial_guidance_visible and current_tutorial_step is not None:
            tutorial_target = get_tutorial_target_position(
                current_tutorial_step,
                npcs,
                camera,
                world_scale,
                screen_size,
            )
            draw_tutorial_arrow(
                window,
                current_tutorial_step,
                tutorial_target,
                tutorial_small_font,
            )
            draw_tutorial_objective_panel(
                window,
                current_tutorial_step,
                helper_font,
                tutorial_small_font,
                recall_notification is not None,
            )
        if nearby_npc is not None and not interface_busy:
            draw_interaction_hint(window, nearby_npc, helper_font)
        if menu_open:
            visible_menu_options = get_menu_options_for_npc(
                menu_npc,
                tutorial_state,
                promise_state,
            )
            menu_height = 44 + len(visible_menu_options) * (
                menu_font.get_linesize() + 10
            )
            draw_menu_box(
                window,
                pygame.Rect(
                    ui_layout.menu.x,
                    ui_layout.menu.y,
                    ui_layout.menu.width,
                    min(menu_height, screen_size[1] - ui_layout.menu.y - ui_layout.margin),
                ),
                visible_menu_options,
                selected_option,
                menu_font,
            )
        if talk_mode == "talk_loading" and talk_future is not None:
            loading_dots = "." * (1 + (pygame.time.get_ticks() // 450) % 3)
            loading_text = talk_pending_player_message or ""
            loading_title = (
                "You confessed" if talk_pending_action == "confess" else "You"
            )
            loading_prompt = (
                f"Confessing and recalling memory{loading_dots}"
                if talk_pending_action == "confess"
                else f"Recalling memory{loading_dots}"
            )
            draw_dialogue_box(
                window,
                ui_layout.dialogue,
                loading_title,
                loading_text,
                dialogue_font,
                helper_font,
                loading_prompt,
            )
            draw_loading_overlay(window, "Recalling memory...", ui_font)
        elif backend_job is not None:
            loading_dots = "." * (1 + (pygame.time.get_ticks() // 450) % 3)
            if backend_job.action == "talk" and backend_job.npc is not None:
                loading_title = "You"
                loading_text = backend_job.player_message
                loading_prompt = (
                    f"{backend_job.npc.display_name} is thinking{loading_dots}"
                )
            elif backend_job.action == "bribe" and backend_job.npc is not None:
                loading_title = "System"
                loading_text = f"Bribing {backend_job.npc.display_name}."
                loading_prompt = f"Updating NPC memory{loading_dots}"
            else:
                loading_title = "System"
                loading_text = "Ending the day and spreading village gossip."
                loading_prompt = f"Consolidating Cognee memory{loading_dots}"
            draw_dialogue_box(
                window,
                ui_layout.dialogue,
                loading_title,
                loading_text,
                dialogue_font,
                helper_font,
                loading_prompt,
            )
            loading_message = (
                "Thinking..."
                if backend_job.action == "talk"
                else "Updating memory..."
            )
            draw_loading_overlay(window, loading_message, ui_font)
        elif reset_confirmation:
            draw_dialogue_box(
                window,
                ui_layout.dialogue,
                "System",
                "Reset demo run? Press Y to confirm, N to cancel.",
                dialogue_font,
                helper_font,
                "Y: Confirm | N/Esc: Cancel",
            )
        elif input_active and input_npc is not None:
            caret = "_" if (pygame.time.get_ticks() // 450) % 2 == 0 else " "
            input_lines = wrap_text(
                f"{input_text}{caret}",
                dialogue_font,
                DIALOGUE_TEXT_WIDTH,
            )
            is_confession_input = input_action == "confess"
            input_instruction = (
                "Type your confession. Enter to submit. Esc to cancel."
                if is_confession_input
                else "Type your message. Enter to send. Esc to cancel."
            )
            if input_error:
                input_display = "\n".join(
                    [input_instruction] + input_lines[-1:] + [input_error]
                )
            else:
                input_display = "\n".join(
                    [input_instruction]
                    + input_lines[-(DIALOGUE_MAX_LINES - 1) :]
                )
            draw_dialogue_box(
                window,
                ui_layout.dialogue,
                (
                    f"Confess to {input_npc.display_name}"
                    if is_confession_input
                    else f"Talk to {input_npc.display_name}"
                ),
                input_display,
                dialogue_font,
                helper_font,
                f"Backspace: Delete | {len(input_text)}/{MAX_PLAYER_INPUT}",
            )
        elif dialogue_pages:
            if len(dialogue_pages) > 1:
                dialogue_prompt = (
                    f"Page {dialogue_page_index + 1}/{len(dialogue_pages)} | "
                    "Space/E/Enter: Next | Esc: Close"
                )
            else:
                dialogue_prompt = "Space/E/Enter: Continue | Esc: Close"
            draw_dialogue_box(
                window,
                ui_layout.dialogue,
                dialogue_title or "System",
                dialogue_pages[dialogue_page_index],
                dialogue_font,
                helper_font,
                dialogue_prompt,
            )

        # The recall notification is deliberately the final UI layer so the
        # world, HUD, menus, and dialogue cannot cover it.
        if recall_notification is not None:
            draw_recall_notification(
                window,
                recall_notification,
                recall_title_font,
                recall_body_font,
            )

        tutorial_popup_page = (
            None
            if tutorial_popup_deferred
            else get_current_popup_page(tutorial_state)
        )
        if tutorial_popup_page is not None:
            draw_tutorial_popup(
                window,
                tutorial_popup_page,
                tutorial_title_font,
                tutorial_body_font,
                tutorial_small_font,
            )

        pygame.display.flip()
        # Pygbag needs an explicit cooperative yield so browser input, drawing,
        # and fetch promises continue while server-side memory work runs.
        await asyncio.sleep(0)

    pygame.key.stop_text_input()
    pygame.quit()


def main() -> None:
    asyncio.run(run_game(browser_mode=False))


if __name__ == "__main__":
    main()
