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


async def show_crash_screen(error_text: str) -> None:
    """Keep the traceback visible instead of falling back to a gray canvas."""
    pygame.init()
    try:
        screen = pygame.display.set_mode((960, 720), pygame.RESIZABLE)
    except Exception:
        screen = pygame.display.set_mode((960, 720))
    pygame.display.set_caption("EchoWorld - Browser Startup Error")
    title_font = pygame.font.Font(None, 38)
    body_font = pygame.font.Font(None, 23)
    wrapped_lines: list[str] = []
    for source_line in error_text.replace("\t", "    ").splitlines():
        wrapped_lines.extend(_wrap_error_line(source_line))
    # Tracebacks end with the actionable exception. Keep that section visible
    # if a browser adds enough loader frames to exceed the canvas height.
    visible_lines = wrapped_lines[-27:]

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
        screen.fill((20, 8, 18))
        pygame.draw.rect(screen, (235, 92, 86), (22, 22, 916, 676), 3)
        title = title_font.render(
            "EchoWorld browser startup failed",
            True,
            (255, 224, 215),
        )
        screen.blit(title, (42, 38))
        hint = body_font.render(
            "Python traceback (most recent lines):",
            True,
            (255, 190, 150),
        )
        screen.blit(hint, (42, 84))
        for index, line in enumerate(visible_lines):
            rendered = body_font.render(line, True, (238, 232, 230))
            screen.blit(rendered, (42, 116 + index * 20))
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
