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

    map_width = 60
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
    for i in [f"You {rch} up from the plumbing, catching a lone human unawares. Now's your chance!","...","Press ? for controls + info.","..."]:
        if i[0] == 'Y':
            c = color.offwhite
        elif i[0] == '.':
            c = color.black
        else:
            c = color.purple
        engine.message_log.add_message(
            i, c
        )

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
            ["(c)ontinue", "(n)ew game", "(h)istory", "(o)ptions", "(q)uit"]
        ):
            if i == 0 and not self.engine:
                continue
            if i == 2 and not len(self.meta.old_runs):
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

        if self.engine:
            history = self.engine.history
            uses = [i for i in history if i[0] in ['use item']]
            kills = [i for i in history if i[0] == 'kill enemy']
            pname = 'player'

            x = 22
            y = 21

            console.print(x,y,pname,color.player)

            console.print(x,y+2,f"Floor: D{self.engine.game_map.floor_number}",color.offwhite)
            console.print(x,y+3,f"Turn:  {self.engine.turn_count}",color.offwhite)


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
        elif event.sym == tcod.event.K_h and len(self.meta.old_runs):
            return HistoryMenu(self)
        elif event.sym == tcod.event.K_o:
            return OptionsMenu(self, self.meta)

        return None

    def start_new_game(self):
        return input_handlers.MainGameEventHandler(new_game(self.meta))


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

class HistoryMenu(SubMenu):
    def __init__(self, parent):
        super().__init__(parent)

        history = self.parent.meta.old_runs
        shistory = [event for run in history for event in run]
        last_run = history[-1]

        stats = {}

        # LAST RUN STATS
        last_run = history[-1]

        stats['Last run'] = [
            ('name', "player"),
            ('won', last_run[-1][0] == "win"),
            ('level', len([i for i in last_run if i[0] == "descend stairs"])+1),
            ('turns', last_run[-1][2]),
            ('unique kills', len(set([i[1] for i in last_run if i[0] == "kill enemy"]))),
            ('items identified', len(set([i[1] for i in last_run if i[0] == "identify item"]))),
            ('killed by', last_run[-1][1])
        ]

        # ALL TIME STATS
        killed_bys = [i[-1][1] for i in history if i[-1][0] == "lose"]

        stats['All time'] = [
            ('turns', sum([i[-1][2] for i in history])),
            ('unique kills', len(set([event[1] for event in shistory if event[0] == "kill enemy"]))), 
            ('items identified', len(set([event[1] for event in shistory if event[0] == "identify item"]))),
            ('nemesis', max(set(killed_bys),key=killed_bys.count) if len(killed_bys) > 0 else "")
        ]

        # RECORDS
        floors = set([event[1] for event in shistory if event[0] == "descend stairs"])
        highest_floor = max(floors) if len(floors) > 0 else 1
        wins = [i for i in history if i[-1][0] == "win"]

        stats['Records'] = [
            ('lowest floor', max(floors) if len(floors) > 0 else 1),
            ('wins', len(wins)),
            ('win %', math.floor((len([i for i in shistory if i[0] == "win"])/len([i for i in shistory if i[0] in ["win","lose"]]))*10000)/100),
            ('fastest win', min([i[-1][2] for i in wins]) if wins else "n/a")
        ]

        self.stats = stats


    def on_render(self, console:tcod.Console) -> None:
        super().on_render(console)
        c2 = color.grey
        c3 = color.offwhite

        console.print(7,7,"HISTORY")

        console.print(8,10,"Last run")
        s = self.stats['Last run']
        console.print(9,12,s[0][1],color.player)
        if s[1][1]:
            console.print(9,13,"WON THE GAME",color.purple)
        else:
            console.print(9,13,f"defeated on floor",c2)
            console.print(27,13,str(s[2][1]),c3)
        y = self.print_subsection(console,s[3:],15,c2,c3)
        
        console.print(8,y+2,"All time")
        y = self.print_subsection(console,self.stats['All time'],y+4,c2,c3)

        y = self.print_subsection(console,self.stats['Records'],y+1,c2,c3)

    def print_subsection(self,console,s,y,c2,c3):
        indent = max([len(i[0]) for i in s])+11
        for k,v in enumerate(s):
            console.print(9,y,f"{v[0]}",c2)
            i = str(v[1])
            c = c3 if i in ['0','n/a','0.0'] else c3
            console.print(indent,y,i,c)
            y += 1
        return y

    
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
        ccstatus = "ON" if self.meta.do_combat_confirm else "OFF"
        console.print(8,12,"(c)onfirm combat start - "+ccstatus)
        tstatus = "ON" if self.meta.tutorials else "OFF"
        console.print(8,14,"(t)utorial messages    - "+tstatus)

        if len(self.meta.tutorial_events) > 0 or self.reset_tutorial_events:
            console.print(8,16,"(r)eset tutorial")
        if self.reset_tutorial_events:
            console.print(31,16,"☑",fg=color.player)

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
        if event.sym == tcod.event.K_c:
            self.meta.do_combat_confirm = not self.meta.do_combat_confirm
        if event.sym == tcod.event.K_t:
            self.meta.tutorials = not self.meta.tutorials
        if event.sym == tcod.event.K_r:
            return input_handlers.Confirm(self,self.do_reset_tutorial_events,"Enable all old tutorial messages?")
        """
        if event.sym == tcod.event.K_d:
            self.meta.difficulty = "normal" if self.meta.difficulty == "easy" else "easy"
            self.difficulty_changed = not self.difficulty_changed
        """
        return super().ev_keydown(event)

    def do_reset_tutorial_events(self):
        self.meta.tutorial_events = []
        self.reset_tutorial_events = True
        return self


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
