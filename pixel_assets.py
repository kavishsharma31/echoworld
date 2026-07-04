"""Original, code-drawn pixel assets for the EchoWorld Pygame frontend."""

from __future__ import annotations

import pygame


BASE_TILE_SIZE = 16


def _finish_tile(surface: pygame.Surface, tile_size: int) -> pygame.Surface:
    """Scale a 16px source tile with nearest-neighbor sampling when requested."""
    if tile_size == BASE_TILE_SIZE:
        return surface
    return pygame.transform.scale(surface, (tile_size, tile_size))


def _shade(color: tuple[int, int, int], amount: int) -> tuple[int, int, int]:
    return tuple(max(0, min(255, channel + amount)) for channel in color)


def make_grass_tile(tile_size: int) -> pygame.Surface:
    tile = pygame.Surface((BASE_TILE_SIZE, BASE_TILE_SIZE))
    tile.fill((74, 142, 72))
    pygame.draw.rect(tile, (84, 155, 79), (1, 2, 2, 1))
    pygame.draw.rect(tile, (57, 121, 59), (5, 11, 1, 3))
    pygame.draw.rect(tile, (95, 163, 84), (10, 5, 2, 1))
    pygame.draw.rect(tile, (55, 119, 57), (14, 13, 1, 2))
    pygame.draw.rect(tile, (88, 154, 78), (3, 7, 1, 1))
    return _finish_tile(tile, tile_size)


def make_path_tile(tile_size: int) -> pygame.Surface:
    tile = pygame.Surface((BASE_TILE_SIZE, BASE_TILE_SIZE))
    tile.fill((186, 159, 104))
    pygame.draw.rect(tile, (211, 184, 125), (1, 2, 5, 3))
    pygame.draw.rect(tile, (164, 137, 89), (6, 2, 1, 3))
    pygame.draw.rect(tile, (169, 141, 91), (0, 7, 16, 1))
    pygame.draw.rect(tile, (201, 175, 116), (8, 9, 6, 3))
    pygame.draw.rect(tile, (159, 132, 85), (7, 9, 1, 3))
    pygame.draw.rect(tile, (212, 184, 124), (2, 13, 4, 2))
    pygame.draw.rect(tile, (167, 140, 88), (11, 14, 2, 1))
    return _finish_tile(tile, tile_size)


def make_tree_tile(tile_size: int) -> pygame.Surface:
    tile = make_grass_tile(BASE_TILE_SIZE)
    pygame.draw.rect(tile, (91, 61, 37), (7, 9, 3, 7))
    pygame.draw.rect(tile, (121, 78, 43), (9, 10, 1, 5))
    pygame.draw.rect(tile, (28, 83, 47), (3, 4, 10, 7))
    pygame.draw.rect(tile, (34, 105, 53), (1, 6, 14, 4))
    pygame.draw.rect(tile, (41, 121, 58), (4, 2, 8, 7))
    pygame.draw.rect(tile, (74, 145, 65), (5, 3, 4, 2))
    pygame.draw.rect(tile, (20, 67, 40), (2, 9, 4, 2))
    return _finish_tile(tile, tile_size)


def make_roof_tile(
    tile_size: int,
    roof_color: tuple[int, int, int],
) -> pygame.Surface:
    tile = pygame.Surface((BASE_TILE_SIZE, BASE_TILE_SIZE))
    tile.fill(roof_color)
    dark = _shade(roof_color, -38)
    light = _shade(roof_color, 24)
    pygame.draw.rect(tile, dark, (0, 0, 16, 2))
    pygame.draw.rect(tile, dark, (0, 7, 16, 1))
    pygame.draw.rect(tile, dark, (0, 14, 16, 2))
    pygame.draw.rect(tile, light, (1, 3, 6, 2))
    pygame.draw.rect(tile, light, (9, 9, 6, 2))
    pygame.draw.rect(tile, dark, (7, 3, 1, 4))
    pygame.draw.rect(tile, dark, (8, 9, 1, 5))
    return _finish_tile(tile, tile_size)


def make_wall_tile(tile_size: int) -> pygame.Surface:
    tile = pygame.Surface((BASE_TILE_SIZE, BASE_TILE_SIZE))
    tile.fill((218, 197, 151))
    pygame.draw.rect(tile, (132, 93, 58), (0, 0, 16, 2))
    pygame.draw.rect(tile, (191, 165, 119), (0, 8, 16, 1))
    pygame.draw.rect(tile, (237, 220, 174), (2, 3, 6, 4))
    pygame.draw.rect(tile, (180, 151, 107), (8, 3, 1, 5))
    pygame.draw.rect(tile, (183, 153, 108), (5, 9, 1, 7))
    pygame.draw.rect(tile, (236, 217, 171), (7, 10, 7, 4))
    pygame.draw.rect(tile, (149, 105, 63), (0, 14, 16, 2))
    return _finish_tile(tile, tile_size)


def make_player_sprite(tile_size: int) -> pygame.Surface:
    sprite = pygame.Surface(
        (BASE_TILE_SIZE, BASE_TILE_SIZE),
        flags=pygame.SRCALPHA,
    )
    pygame.draw.ellipse(sprite, (24, 35, 31, 120), (3, 13, 10, 3))
    pygame.draw.rect(sprite, (57, 47, 43), (4, 12, 3, 3))
    pygame.draw.rect(sprite, (57, 47, 43), (9, 12, 3, 3))
    pygame.draw.rect(sprite, (42, 84, 137), (4, 7, 8, 6))
    pygame.draw.rect(sprite, (76, 126, 181), (5, 7, 6, 2))
    pygame.draw.rect(sprite, (225, 173, 121), (3, 8, 2, 4))
    pygame.draw.rect(sprite, (225, 173, 121), (11, 8, 2, 4))
    pygame.draw.rect(sprite, (229, 181, 129), (5, 3, 6, 5))
    pygame.draw.rect(sprite, (84, 54, 38), (5, 2, 6, 2))
    pygame.draw.rect(sprite, (84, 54, 38), (4, 3, 2, 3))
    pygame.draw.rect(sprite, (38, 40, 43), (6, 5, 1, 1))
    pygame.draw.rect(sprite, (38, 40, 43), (9, 5, 1, 1))
    pygame.draw.rect(sprite, (188, 53, 47), (11, 7, 2, 2))
    return _finish_tile(sprite, tile_size)


def make_npc_sprite(
    tile_size: int,
    color: tuple[int, int, int],
    apron: bool = False,
    helmet: bool = False,
    elder: bool = False,
) -> pygame.Surface:
    sprite = pygame.Surface(
        (BASE_TILE_SIZE, BASE_TILE_SIZE),
        flags=pygame.SRCALPHA,
    )
    dark = _shade(color, -45)
    light = _shade(color, 28)
    skin = (220, 169, 117)

    pygame.draw.ellipse(sprite, (24, 35, 31, 120), (3, 13, 10, 3))
    pygame.draw.rect(sprite, dark, (4, 12, 3, 3))
    pygame.draw.rect(sprite, dark, (9, 12, 3, 3))
    pygame.draw.rect(sprite, color, (4, 7, 8, 6))
    pygame.draw.rect(sprite, light, (5, 7, 6, 2))
    pygame.draw.rect(sprite, skin, (3, 8, 2, 4))
    pygame.draw.rect(sprite, skin, (11, 8, 2, 4))
    pygame.draw.rect(sprite, skin, (5, 3, 6, 5))
    pygame.draw.rect(sprite, (65, 46, 38), (5, 2, 6, 2))
    pygame.draw.rect(sprite, (35, 36, 38), (6, 5, 1, 1))
    pygame.draw.rect(sprite, (35, 36, 38), (9, 5, 1, 1))

    if apron:
        pygame.draw.rect(sprite, (230, 215, 177), (6, 8, 5, 5))
        pygame.draw.rect(sprite, (167, 145, 110), (6, 8, 5, 1))
    if helmet:
        pygame.draw.rect(sprite, (126, 138, 151), (4, 2, 8, 3))
        pygame.draw.rect(sprite, (80, 93, 108), (4, 4, 2, 3))
        pygame.draw.rect(sprite, (182, 192, 199), (6, 2, 4, 1))
    if elder:
        pygame.draw.rect(sprite, (231, 226, 208), (5, 6, 6, 5))
        pygame.draw.rect(sprite, (203, 196, 181), (6, 10, 4, 2))
        pygame.draw.rect(sprite, (111, 75, 43), (13, 6, 1, 9))
        pygame.draw.rect(sprite, (151, 107, 57), (12, 5, 2, 2))

    return _finish_tile(sprite, tile_size)


def make_exclamation_bubble(tile_size: int) -> pygame.Surface:
    bubble = pygame.Surface(
        (BASE_TILE_SIZE, BASE_TILE_SIZE),
        flags=pygame.SRCALPHA,
    )
    pygame.draw.rect(bubble, (35, 30, 34), (4, 1, 9, 10))
    pygame.draw.rect(bubble, (250, 245, 214), (3, 0, 9, 10))
    pygame.draw.rect(bubble, (250, 245, 214), (7, 10, 3, 2))
    pygame.draw.rect(bubble, (183, 48, 45), (7, 2, 2, 4))
    pygame.draw.rect(bubble, (183, 48, 45), (7, 7, 2, 2))
    return _finish_tile(bubble, tile_size)


def _wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
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


def draw_dialogue_box(
    surface: pygame.Surface,
    rect: pygame.Rect | tuple[int, int, int, int],
    title: str,
    text: str,
    font: pygame.font.Font,
    small_font: pygame.font.Font,
    prompt: str = "Press Space/E to continue",
) -> None:
    box = pygame.Rect(rect)
    pygame.draw.rect(surface, (16, 20, 28), box)
    pygame.draw.rect(surface, (235, 222, 178), box, 4)
    pygame.draw.rect(surface, (92, 104, 105), box.inflate(-14, -14), 2)

    padding = 24
    title_image = font.render(title, True, (247, 205, 104))
    title_position = (box.x + padding, box.y + 14)
    surface.blit(title_image, title_position)

    separator_y = title_position[1] + title_image.get_height() + 8
    pygame.draw.line(
        surface,
        (92, 104, 105),
        (box.x + padding, separator_y),
        (box.right - padding, separator_y),
        2,
    )

    prompt_image = small_font.render(prompt, True, (174, 184, 177))
    prompt_y = box.bottom - prompt_image.get_height() - 14
    text_y = separator_y + 12
    line_height = font.get_linesize()
    max_lines = max(1, (prompt_y - text_y - 8) // line_height)
    wrapped = _wrap_text(text, font, box.width - padding * 2)
    visible_lines = wrapped[:max_lines]
    if len(wrapped) > max_lines and visible_lines:
        final_line = visible_lines[-1]
        while final_line and font.size(f"{final_line}…")[0] > box.width - padding * 2:
            final_line = final_line[:-1]
        visible_lines[-1] = f"{final_line.rstrip()}…"

    for index, line in enumerate(visible_lines):
        line_image = font.render(line, True, (240, 239, 224))
        surface.blit(line_image, (box.x + padding, text_y + index * line_height))

    surface.blit(
        prompt_image,
        (box.right - prompt_image.get_width() - padding, prompt_y),
    )


def draw_menu_box(
    surface: pygame.Surface,
    rect: pygame.Rect | tuple[int, int, int, int],
    options: list[str] | tuple[str, ...],
    selected_index: int,
    font: pygame.font.Font,
) -> None:
    box = pygame.Rect(rect)
    pygame.draw.rect(surface, (18, 22, 30), box)
    pygame.draw.rect(surface, (235, 222, 178), box, 4)
    pygame.draw.rect(surface, (85, 96, 98), box.inflate(-14, -14), 2)

    line_height = font.get_linesize() + 10
    start_y = box.y + 20
    for index, option in enumerate(options):
        option_y = start_y + index * line_height
        if index == selected_index:
            highlight = pygame.Rect(
                box.x + 14,
                option_y - 4,
                box.width - 28,
                line_height,
            )
            pygame.draw.rect(surface, (64, 82, 86), highlight)
            pygame.draw.rect(surface, (123, 137, 127), highlight, 2)
            marker = font.render(">", True, (247, 205, 104))
            surface.blit(marker, (box.x + 24, option_y))
        option_image = font.render(option, True, (241, 239, 220))
        surface.blit(option_image, (box.x + 56, option_y))
