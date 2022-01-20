"""Handle the loading and initialization of game sessions."""
from __future__ import annotations

import math
import copy
import lzma
import pickle
import traceback
from typing import Optional
import random

import tcod

from game.engine import Engine
from game import color, entity_factories, exceptions, input_handlers
from game.game_map import GameWorld

import utils


# Load the background image and remove the alpha channel.
background_image = tcod.image.load(utils.get_resource("menu_background.png"))[:, :, :3]

def new_game(meta) -> Engine:
    """Return a brand new game session as an Engine instance."""

    # If there's an existing save, log it as a game over
    try:
        engine = load_game(utils.get_resource("savegame.sav"))
    except FileNotFoundError:
        engine = None

    if engine:
        # make sure there's meta continuity when logging the run
        engine.meta = meta
        engine.history.append(("lose","scumming",engine.turn_count))
        engine.log_run()
        meta = engine.meta

    map_width = 57
    map_height = 50

    player = copy.deepcopy(entity_factories.player)
    player.id = 0

    engine = Engine(player=player, meta=meta)
    engine.turn_count = 240

    game_mode = 'default'
    # game_mode = 'overview'
    # game_mode = 'consumable testing'
    # game_mode = 'god mode'

    engine.game_world = GameWorld(
        engine=engine,
        map_width=map_width,
        map_height=map_height,
        game_mode=game_mode
    )

    engine.game_world.generate_floor()
    engine.update_fov()

    rch = random.choice(["splorch","splurch","lurch","splash","schlop","shlorp","splosh"])
    engine.message_log.add_message(f"You {rch} up from the plumbing, catching a lone human unawares. Now's your chance!",color.offwhite)
    engine.message_log.add_message("Press ? for controls + info.",color.purple)

    return engine

def load_game(filename: str) -> Engine:
    """Load an Engine instance from a file."""
    with open(filename, "rb") as f:
        engine = pickle.loads(lzma.decompress(f.read()))
    assert isinstance(engine, Engine)
    return engine

def load_settings(filename: str) -> Meta:
    with open(filename, "rb") as f:
        meta = pickle.loads(lzma.decompress(f.read()))
    assert isinstance(meta, Meta)
    return meta

class MainMenu(input_handlers.BaseEventHandler):
    """Handle the main menu rendering and input."""

    def __init__(self):
        try:
            self.engine = load_game(utils.get_resource("savegame.sav"))
        except FileNotFoundError:
            self.engine = None

        try:
            self.meta = Meta(load_settings(utils.get_resource("savemeta.sav")))
        except FileNotFoundError:
            self.meta = Meta()

        if self.engine:
            self.engine.meta = self.meta

    def on_render(self, console: tcod.Console) -> None:
        """Render the main menu on a background image."""
        console.draw_semigraphics(background_image, 0, 0)

        console.print(
            console.width - 16,
            console.height - 3,
            "by -taq",
            fg=color.purple,
            alignment=tcod.CENTER,
        )

        menu_width = 24
        for i, text in enumerate(
            ["(c)ontinue", "(n)ew game", "(o)ptions", "(q)uit"]
        ):
            if i == 0 and not self.engine:
                continue
            console.print(
                72,
                19 + (2*i),
                text.ljust(menu_width),
                fg=color.white,
                bg=color.black,
                alignment=tcod.CENTER,
                bg_blend=tcod.BKGND_ALPHA(64),
            )


    def ev_keydown(
        self, event: tcod.event.KeyDown
    ) -> Optional[input_handlers.BaseEventHandler]:
        if event.sym in (tcod.event.K_q, tcod.event.K_ESCAPE):
            raise SystemExit()
        elif event.sym == tcod.event.K_c:
            if self.engine:
                return input_handlers.MainGameEventHandler(self.engine)
            else:
                return input_handlers.PopupMessage(self, "No saved game to load.")
        elif event.sym == tcod.event.K_n:
            if self.engine:
                return input_handlers.Confirm(parent=self,callback=self.start_new_game,prompt="Start a new game? Your existing save will be overwritten and marked as a loss.")
            else: return self.start_new_game()
        elif event.sym == tcod.event.K_o:
            return OptionsMenu(self, self.meta)

        return None

    def start_new_game(self):
        raise exceptions.NewGame(self.meta)

class SubMenu(input_handlers.BaseEventHandler):
    def __init__(self, parent):
        self.parent = parent

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[input_handlers.BaseEventHandler]:
        if event.sym == tcod.event.K_ESCAPE:
            return self.parent
        return None

    def on_render(self, console:tcod.Console) -> None:
        console.draw_semigraphics(background_image, 0, 0)
        console.print(7,47,"(ESC) to go back")

    
class OptionsMenu(SubMenu):
    def __init__(self, parent, meta):
        super().__init__(parent)
        self.meta = meta
        self.reset_tutorial_events = False
        self.difficulty_changed = False

    def on_render(self, console:tcod.Console) -> None:
        super().on_render(console)
        console.print(7,7,"OPTIONS")
        console.print(8,10,"(f)ullscreen")
        tstatus = "ON" if self.meta.tutorials else "OFF"

        """
        dstatus = "EASY" if self.meta.difficulty == "easy" else "NORMAL"
        console.print(8,18,"(d)ifficulty           - "+dstatus)
        if self.difficulty_changed:
            console.print(8,20,"difficulty change takes effect on new game",color.grey)
        """

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[input_handlers.BaseEventHandler]:
        if event.sym == tcod.event.K_f:
            self.meta.fullscreen = not self.meta.fullscreen
            raise exceptions.ToggleFullscreen()
        
        return super().ev_keydown(event)


class Meta():
    version = "0.0"

    _fullscreen = True
    _do_combat_confirm = True
    _tutorials = True
    _difficulty = "easy"
    old_runs = []
    tutorial_events = []

    def __init__(self, old_meta=None):
        def override(name):
            if hasattr(old_meta,name):
                setattr(self,name,getattr(old_meta,name))

        if old_meta:
            for i in ['_fullscreen','_do_combat_confirm','_tutorials','_difficulty','old_runs','tutorial_events']:
                override(i)

        self.save()

    @property
    def do_combat_confirm(self):
        return self._do_combat_confirm

    @do_combat_confirm.setter
    def do_combat_confirm(self,new_val):
        self._do_combat_confirm = new_val
        self.save()

    @property
    def fullscreen(self):
        return self._fullscreen

    @fullscreen.setter
    def fullscreen(self, new_val):
        self._fullscreen = new_val
        self.save()

    @property
    def tutorials(self):
        return self._tutorials

    @tutorials.setter
    def tutorials(self,new_val):
        self._tutorials = new_val
        self.save()

    @property
    def difficulty(self):
        return self._difficulty

    @difficulty.setter
    def difficulty(self, new_val):
        self._difficulty = new_val
        self.save()

    def log_tutorial_event(self,event):
        self.tutorial_events.append(event)
        self.save()

    def log_run(self, history):
        self.old_runs.append(history)
        self.save()

    def save(self):
        save_data = lzma.compress(pickle.dumps(self))
        with open(utils.get_resource("savemeta.sav"), "wb") as f:
            f.write(save_data)
