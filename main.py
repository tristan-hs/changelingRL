#!/usr/bin/env python3
import traceback
import warnings
import tcod

from game import color, exceptions
from game.game_map import GameMap
from game import input_handlers, setup_game

import utils


def save_game(handler: input_handlers.BaseEventHandler, filename: str) -> None:
    """If the current event handler has an active Engine then save it."""
    if isinstance(handler, input_handlers.EventHandler):
        handler.engine.save_as(filename)

def toggle_fullscreen(context: tcod.context.Context) -> None:
    """Toggle a context window between fullscreen and windowed modes."""
    if not context.sdl_window_p:
        return
    fullscreen = tcod.lib.SDL_GetWindowFlags(context.sdl_window_p) & (
        tcod.lib.SDL_WINDOW_FULLSCREEN | tcod.lib.SDL_WINDOW_FULLSCREEN_DESKTOP
    )
    tcod.lib.SDL_SetWindowFullscreen(
        context.sdl_window_p,
        0 if fullscreen else tcod.lib.SDL_WINDOW_FULLSCREEN_DESKTOP,
    )

def main() -> None:
    screen_width = 80
    screen_height = 50

    tileset = tcod.tileset.load_tilesheet(
        utils.get_resource("tiles2.png"), 16,16, tcod.tileset.CHARMAP_CP437
    )

    handler: input_handlers.BaseEventHandler = setup_game.MainMenu()

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=RuntimeWarning)
        with tcod.context.new_terminal(
            screen_width,
            screen_height,
            tileset=tileset,
            title="Game",
            vsync=True,
            renderer=tcod.RENDERER_SDL2
        ) as context:
            root_console = tcod.Console(screen_width, screen_height, order="F")
            if handler.meta.fullscreen:
                toggle_fullscreen(context)
            try:
                while True:
                    root_console.clear()
                    handler.on_render(console=root_console)
                    context.present(root_console)

                    try:
                        for event in tcod.event.wait(None):
                            context.convert_event(event)
                            handler = handler.handle_events(event)

                    except exceptions.NewGame as e:
                        root_console.clear()
                        root_console.print(32,24,"Loading level...")
                        context.present(root_console)

                        handler = input_handlers.MainGameEventHandler(setup_game.new_game(e.meta))

                    except exceptions.ToggleFullscreen:
                        toggle_fullscreen(context)
                        if hasattr(handler,'engine'):
                            handler.engine.meta.fullscreen = not handler.engine.meta.fullscreen

                    except exceptions.QuitToMenu:
                        save_game(handler, utils.get_resource("savegame.sav"))
                        handler = setup_game.MainMenu()

                    except exceptions.QuitWithoutSaving:
                        handler = setup_game.MainMenu()

                    except Exception:  # Handle exceptions in game.
                        traceback.print_exc()  # Print error to stderr.
                        # Then print the error to the message log.
                        if isinstance(handler, input_handlers.EventHandler):
                            handler.engine.message_log.add_message(
                                traceback.format_exc(), color.red
                            )

            except SystemExit:  # Save and quit.
                save_game(handler, utils.get_resource("savegame.sav"))
                raise
            except BaseException:  # Save on any other unexpected exception.
                save_game(handler, utils.get_resource("savegame.sav"))
                raise


if __name__ == "__main__":
    main()