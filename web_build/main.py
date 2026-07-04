"""Pygbag entrypoint with a persistent, visible startup crash screen."""

import asyncio
import traceback

import pygame


print("[web] main.py loaded")


def _wrap_error_line(text: str, max_characters: int = 96) -> list[str]:
    if not text:
        return [""]
    return [
        text[index : index + max_characters]
        for index in range(0, len(text), max_characters)
    ]


def _browser_canvas_size() -> tuple[int, int]:
    try:
        import platform

        density = max(1.0, min(3.0, float(platform.window.devicePixelRatio)))
        width = round(float(platform.window.innerWidth) * density)
        height = round(float(platform.window.innerHeight) * density)
    except Exception:
        return (1280, 720)
    if width < 320 or height < 240:
        return (1280, 720)
    return (width, height)


async def show_crash_screen(error_text: str) -> None:
    """Keep the traceback visible instead of falling back to a gray canvas."""
    pygame.init()
    display_size = _browser_canvas_size()
    try:
        screen = pygame.display.set_mode(display_size, pygame.RESIZABLE)
    except Exception:
        screen = pygame.display.set_mode(display_size)
    pygame.display.set_caption("EchoWorld - Browser Startup Error")

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
        requested_size = _browser_canvas_size()
        if requested_size != screen.get_size():
            screen = pygame.display.set_mode(requested_size, pygame.RESIZABLE)

        screen_w, screen_h = screen.get_size()
        scale = max(1.0, min(3.0, min(screen_w / 1280, screen_h / 720)))
        px = lambda value: max(1, round(value * scale))
        title_font = pygame.font.Font(None, px(38))
        body_font = pygame.font.Font(None, px(23))
        max_characters = max(36, (screen_w - px(84)) // max(7, px(11)))
        wrapped_lines: list[str] = []
        for source_line in error_text.replace("\t", "    ").splitlines():
            wrapped_lines.extend(_wrap_error_line(source_line, max_characters))
        max_lines = max(5, (screen_h - px(140)) // body_font.get_linesize())
        visible_lines = wrapped_lines[-max_lines:]

        screen.fill((20, 8, 18))
        border = pygame.Rect(px(22), px(22), screen_w - px(44), screen_h - px(44))
        pygame.draw.rect(screen, (235, 92, 86), border, px(3))
        title = title_font.render(
            "EchoWorld browser startup failed",
            True,
            (255, 224, 215),
        )
        screen.blit(title, (px(42), px(38)))
        hint = body_font.render(
            "Python traceback (most recent lines):",
            True,
            (255, 190, 150),
        )
        screen.blit(hint, (px(42), px(84)))
        for index, line in enumerate(visible_lines):
            rendered = body_font.render(line, True, (238, 232, 230))
            screen.blit(
                rendered,
                (px(42), px(116) + index * body_font.get_linesize()),
            )
        pygame.display.flip()
        await asyncio.sleep(0)


async def main() -> None:
    try:
        print("[web] importing game_app")
        from game_app import run_game

        print("[web] starting run_game(browser_mode=True)")
        await run_game(browser_mode=True)
    except Exception:
        error_text = traceback.format_exc()
        print(error_text)
        await show_crash_screen(error_text)


asyncio.run(main())
