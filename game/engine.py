from __future__ import annotations

import lzma
import pickle
import os

from typing import TYPE_CHECKING

from tcod.console import Console
from tcod.map import compute_fov

from game import exceptions, render_functions
from game.actions import WaitAction, BumpAction
from game.message_log import MessageLog
import game.color as color
from game.render_order import RenderOrder
from game.exceptions import Impossible
from game.entity import Actor

if TYPE_CHECKING:
    from game.game_map import GameMap, GameWorld

import utils


class Engine:
    game_map: GameMap
    game_world: GameWorld
 
    def __init__(self, player: Actor, meta):
        self.message_log = MessageLog(self)
        self.mouse_location = (0, 0)
        self.player = player
        self.turn_count = 0
        self.show_instructions = True if len(meta.old_runs) < 10 else False
        self.meta = meta
        self.confirmed_in_combat = False
        self.difficulty = meta.difficulty

        self.history = []

    def log_run(self):
        self.meta.log_run(self.history)

    # field of view
    @property
    def fov_radius(self):
        return 8

    # field of sense -- through walls
    @property
    def fos_radius(self):
        return 0

    # field of identity -- through walls
    @property
    def foi_radius(self):
        return 0

    @property
    def in_combat(self):
        return self.can_see_enemies

    @property
    def can_see_enemies(self):
        return len([a for a in self.fov_actors]) > 0

    @property
    def stairs_visible(self):
        return self.game_map.visible[self.game_map.downstairs_location]

    def handle_enemy_turns(self) -> None:
        enemies = sorted(set(self.game_map.actors) - {self.player}, key=lambda x: x.id)

        # enemy turns
        for entity in enemies:
            if entity.ai:
                try: 
                    entity.ai.perform()
                except exceptions.Impossible:
                    pass

                if not self.player.is_alive:
                    return

        # enemy post-turns
        for entity in enemies:
            if entity.ai:
                entity.on_turn()

        # player post-turn
        self.player.on_turn()
        
        self.turn_count += 1

    @property
    def fov(self):
        return compute_fov(
            self.game_map.tiles["transparent"],
            (self.player.x, self.player.y),
            radius=self.fov_radius,
        )

    @property
    def fov_actors(self):
        return [actor for actor in 
            sorted(list(self.game_map.actors),key=lambda a:a.id) if
            not actor is self.player and (
                self.game_map.visible[actor.x,actor.y] or 
                self.game_map.smellable(actor,True)
            )
        ]

    @property
    def mouse_things(self):
        entities = [
            e for e in self.game_map.entities if 
                (e.x,e.y) == self.mouse_location and 
                (
                    self.game_map.visible[e.x,e.y] or 
                    (self.game_map.explored[e.x,e.y] and e.render_order == RenderOrder.ITEM) or
                    self.game_map.smellable(e, True)
                )
        ]

        x,y = self.mouse_location
        if self.game_map.visible[x,y] or self.game_map.explored[x,y] or self.game_map.mapped[x,y]:
            entities += [self.game_map.tiles[x,y]]

        return entities


    def update_fov(self) -> None:
        """Recompute the visible area based on the players point of view."""
        self.game_map.visible[:] = self.fov
        # If a tile is "visible" it should be added to "explored".
        self.game_map.explored |= self.game_map.visible


    @property
    def do_turn_count(self):
        for e in self.game_map.items:
            if e.x > 72 and e.y < 5 and self.game_map.explored[e.x,e.y]:
                return False
        for x in range(72,76):
            for y in range(5):
                if self.game_map.visible[x,y]:
                    return False
        return True

    def render(self, console: Console) -> None:
        # all boxes 9 high
        # left box: 20 w (0,41)
        # mid: 40 w (21,41)
        # right: 18 w (62,41)

        self.game_map.render(console)

        render_functions.render_dungeon_level(
            console=console,
            dungeon_level=self.game_world.current_floor,
            location=(76,0),
            turn_count = self.turn_count,
            do_turn_count = self.do_turn_count
        )

        # MIDDLE PANEL
        self.message_log.render(console=console, x=18, y=41, width=43, height=9)

        # LEFT PANEL
        looking = self.mouse_location != (0,0)
        if looking:
            actor = self.game_map.get_actor_at_location(*self.mouse_location)
            if actor:
                self.game_map.print_enemy_fov(console, actor)
            render_functions.render_names_at_mouse_location(
                console=console, x=0, y=41, engine=self
            )

        elif self.show_instructions:
            render_functions.render_instructions(
                console=console,
                location=(0,41)
            )

        else:
            render_functions.print_fov_actors(console,self.player,(0,41))
            pass


    def save_as(self, filename: str) -> None:
        """Save this Engine instance as a compressed file."""
        meta = self.meta
        self.meta = None
        save_data = lzma.compress(pickle.dumps(self))
        with open(filename, "wb") as f:
            f.write(save_data)
        self.meta = meta
        