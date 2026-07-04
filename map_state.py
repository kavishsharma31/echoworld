MAP_ROWS = 7
MAP_COLS = 7

DEFAULT_PLAYER_POS = {"row": 3, "col": 3}

NPC_POSITIONS = {
    "blacksmith": {"row": 1, "col": 2},
    "guard": {"row": 1, "col": 5},
    "merchant": {"row": 3, "col": 1},
    "elder": {"row": 5, "col": 3},
}

NPC_ICONS = {
    "blacksmith": "⚒️",
    "guard": "🛡️",
    "merchant": "🏪",
    "elder": "🧙",
}

TERRAIN_ICONS = {
    "player": "🧍",
    "empty": "⬜",
    "tree": "🌲",
    "village_hall": "🏛️",
}

NPC_PRIORITY = ["blacksmith", "merchant", "guard", "elder"]


def clamp_position(row: int, col: int) -> dict:
    return {
        "row": max(0, min(MAP_ROWS - 1, row)),
        "col": max(0, min(MAP_COLS - 1, col)),
    }


def move_player(position: dict, direction: str) -> dict:
    row = position["row"]
    col = position["col"]

    if direction == "up":
        row -= 1
    elif direction == "down":
        row += 1
    elif direction == "left":
        col -= 1
    elif direction == "right":
        col += 1

    return clamp_position(row, col)


def manhattan_distance(a: dict, b: dict) -> int:
    return abs(a["row"] - b["row"]) + abs(a["col"] - b["col"])


def get_nearby_npc(position: dict) -> str | None:
    nearby = []

    for npc_key in NPC_PRIORITY:
        npc_pos = NPC_POSITIONS[npc_key]
        distance = manhattan_distance(position, npc_pos)

        if distance <= 1:
            nearby.append((distance, NPC_PRIORITY.index(npc_key), npc_key))

    if not nearby:
        return None

    nearby.sort()
    return nearby[0][2]


def render_map(position: dict) -> list[list[str]]:
    grid = []

    for row in range(MAP_ROWS):
        current_row = []

        for col in range(MAP_COLS):
            is_border = row == 0 or row == MAP_ROWS - 1 or col == 0 or col == MAP_COLS - 1

            if row == 6 and col == 3:
                icon = TERRAIN_ICONS["village_hall"]
            elif is_border:
                icon = TERRAIN_ICONS["tree"]
            else:
                icon = TERRAIN_ICONS["empty"]

            current_row.append(icon)

        grid.append(current_row)

    for npc_key, npc_pos in NPC_POSITIONS.items():
        grid[npc_pos["row"]][npc_pos["col"]] = NPC_ICONS[npc_key]

    grid[position["row"]][position["col"]] = TERRAIN_ICONS["player"]

    return grid


def map_to_text(position: dict) -> str:
    grid = render_map(position)
    return "\n".join(" ".join(row) for row in grid)


if __name__ == "__main__":
    print(map_to_text(DEFAULT_PLAYER_POS))
    print("Nearby NPC:", get_nearby_npc(DEFAULT_PLAYER_POS))
