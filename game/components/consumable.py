from __future__ import annotations

from typing import Optional, TYPE_CHECKING
import random
import math
import numpy as np

from game import actions, color, exceptions

import game.components.ai

from game.components.base_component import BaseComponent
from game.exceptions import Impossible
from game.input_handlers import (
    ActionOrHandler,
    AreaRangedAttackHandler,
    SingleRangedAttackHandler,
    SingleDrillingProjectileAttackHandler,
    SingleProjectileAttackHandler
)
from game.components.status_effect import *
import game.tile_types as tile_types


if TYPE_CHECKING:
    from game.entity import Actor, Item


class Consumable(BaseComponent):
    parent: Item
    saved_stats=False

    @property
    def template(self):
        return not hasattr(self.parent,'parent')

    @property
    def modified_damage(self):
        return self.damage

    # MUST OVERRIDE ONE OF THESE TWO PROPERTIES:

    # list of tuples (string, color)
    @property
    def description_parts(self):
        return [(self.description, color.offwhite)]

    # string
    @property
    def description(self):
        return ''.join([str(i[0]) for i in self.description_parts])

    def get_use_action(self, consumer: Actor) -> Optional[ActionOrHandler]:
        """Try to return the action for this item."""
        return actions.ItemAction(consumer, self.parent)

    def start_activation(self,action):
        self.save_stats()
        self.consume()

        try:
            self.activate(action)
        except exceptions.UnorderedPickup:
            self.identify()
            self.unsave_stats()
            raise
        except Exception:
            self.unsave_stats()
            raise
        else:
            self.identify()
            self.unsave_stats()

    # ensure pre-consumption stats are used to modify item effects
    def save_stats(self):
        # implement
        self.saved_stats = True

    def unsave_stats(self):
        self.saved_stats = False

    def activate(self, action: actions.ItemAction) -> None:
        """Invoke this items ability.

        `action` is the context for this activation.
        """
        raise NotImplementedError()

    def consume(self, force=False) -> None:
        """Remove the consumed item from its containing inventory."""
        self.parent.consume()

    def identify(self) -> None:
        self.parent.identified = True

    def apply_status(self, action, status) -> None:
        st = [s for s in action.target_actor.statuses if isinstance(s,status)]
        if st:
            st[0].strengthen()
        else:
            st = status(action.target_actor)


class Projectile(Consumable):

    def __init__(self,damage=1):
        self.damage = damage

    def get_use_action(self, consumer: Actor) -> Optional[ActionOrHandler]:
        self.engine.message_log.add_message("Select a target.", color.cyan)
        seeking = "anything"
        return SingleProjectileAttackHandler(
            self.engine,
            callback=lambda xy: actions.ThrowItem(consumer, self.parent, xy),
            seeking=seeking,
            pathfinder=self.get_path_to
        )

    def activate(self, action: actions.ItemAction) -> None:
        """ Override this part"""
        consumer = action.entity
        target = action.target_actor if action.target_actor else action.target_item

        if target and not target.is_boss:
            self.engine.message_log.add_message(
                    f"{target.label} takes {self.modified_damage} damage!", color.offwhite
            )
            target.take_damage(self.modified_damage)
        else:
            self.engine.message_log.add_message("Nothing happens.", color.grey)

    def get_path_to(self, dest_x, dest_y, walkable=True):
        """versatile bresenham"""
        gm = self.gamemap
        tiles = gm.tiles['walkable'] if walkable else np.full((gm.width,gm.height),fill_value=True,order="F")
        tiles = np.array(tiles, dtype=np.bool)

        for entity in gm.entities:
            if entity.blocks_movement:
                tiles[entity.x,entity.y] = False

        path = []
        start = loc = [self.engine.player.x, self.engine.player.y]
        dest = [dest_x, dest_y]
        dist = [abs(dest[0]-loc[0]), abs(dest[1]-loc[1])]

        a = 1 if dist[1] > dist[0] else 0
        b = 1 if a == 0 else 0

        D = (2 * dist[b]) - dist[a]

        while loc != [dest_x, dest_y] and len(path) < 100:
            if dest[a] > loc[a]:
                loc[a] += 1
            if dest[a] < loc[a]:
                loc[a] -= 1

            if D > 0:
                if dest[b] > loc[b]:
                    loc[b] += 1
                if dest[b] < loc[b]:
                    loc[b] -= 1                    
                D = D - (2*dist[a])

            D = D + (2*dist[b])

            path.append((loc[0],loc[1]))
            if not tiles[loc[0],loc[1]] and walkable:
                break

        return path

    def get_path_past(self, dest_x, dest_y, walkable=True):
        path = self.get_path_to(dest_x,dest_y,walkable)
        if len(path) < 1:
            return path

        new_path = []
        i = 0

        while True:
            key = i % len(path)
            tile = path[key]
            if key == 0:
                diff = (tile[0]-self.engine.player.x,tile[1]-self.engine.player.y)
            else:
                prev = path[key-1]
                diff = (tile[0]-prev[0],tile[1]-prev[1])

            new_o = new_path[i-1] if i > 0 else (dest_x,dest_y)
            new_tile = (new_o[0]+diff[0],new_o[1]+diff[1])

            if not self.engine.game_map.tile_is_walkable(*new_tile):
                break
            new_path.append(new_tile)
            i += 1

        return new_path


class DamagingProjectile(Projectile):
    @property
    def description_parts(self):
        d = self.modified_damage if not self.template else self.damage
        return [("projectile, ", color.offwhite), (d, color.bile), (" dmg", color.offwhite)]
