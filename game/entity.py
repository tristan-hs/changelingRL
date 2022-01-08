from __future__ import annotations

import copy
import math
import random
from typing import Optional, Tuple, Type, TypeVar, TYPE_CHECKING, Union, Set

from tcod.map import compute_fov

from game.render_order import RenderOrder

from game import color as Color

from game.components.inventory import Inventory
from game.components import consumable

from game.render_functions import DIRECTIONS

from game.actions import ActionWithDirection

if TYPE_CHECKING:
    from game.components.ai import BaseAI
    from game.game_map import GameMap
    from game.engine import Engine

T = TypeVar("T", bound="Entity")


class Entity:
    """
    A generic object to represent players, enemies, items, etc.
    """

    parent: Union[GameMap, Inventory]

    def __init__(
        self,
        parent: Optional[GameMap] = None,
        x: int = 0,
        y: int = 0,
        char: str = "?",
        color: Tuple[int, int, int] = (255, 255, 255),
        name: str = "<Unnamed>",
        blocks_movement: bool = False,
        render_order: RenderOrder = RenderOrder.CORPSE,
        description: str = None,
        flavor: str = None
    ):
        self.x = x
        self.y = y
        self.char = char
        self.color = color
        self.name = name
        self.blocks_movement = blocks_movement
        self.render_order = render_order
        self._description=description
        self._flavor = flavor
        if parent:
            # If parent isn't provided now then it will be set later.
            self.parent = parent
            parent.entities.add(self)

    @property
    def char(self):
        return self._char

    @char.setter
    def char(self,new_val):
        self._char = new_val

    @property
    def gamemap(self) -> GameMap:
        return self.parent.gamemap

    @property
    def xy(self) -> Tuple[int, int]:
        return (self.x, self.y)

    @property
    def engine(self) -> Engine:
        return self.gamemap.engine

    @property
    def label(self) -> str:
        return self.name

    @property
    def description(self) -> str:
        return self._description

    @property
    def flavor(self):
        return self._flavor
  
    def spawn(self: T, gamemap: GameMap, x: int, y: int) -> T:
        """Spawn a copy of this instance at the given location."""
        clone = copy.deepcopy(self)
        clone.x = x
        clone.y = y
        clone.parent = gamemap
        clone.id = gamemap.next_id
        clone.preSpawn()
        gamemap.entities.add(clone)
        return clone

    def preSpawn(self):
        return

    def place(self, x: int, y: int, gamemap: Optional[GameMap] = None) -> None:
        """Place this entity at a new location.  Handles moving across GameMaps."""
        self.x = x
        self.y = y
        if gamemap:
            if hasattr(self, "parent"):  # Possibly uninitialized.
                if self.parent is self.gamemap:
                    self.gamemap.entities.remove(self)
            self.parent = gamemap
            gamemap.entities.add(self)

    def distance(self, x: int, y: int) -> float:
        """
        Return the distance between the current entity and the given (x, y) coordinate.
        """
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

    def move(self, dx: int, dy: int) -> None:
        # Move the entity by a given amount
        footprint = self.xy

        self.x += dx
        self.y += dy

    def is_next_to_player(self):
        for d in DIRECTIONS:
            if self.gamemap.get_actor_at_location(d[0]+self.x,d[1]+self.y) is self.engine.player:
                return True
        return False

    def get_adjacent_actors(self)->List[Actor]:
        actors = []
        for d in DIRECTIONS:
            a = self.gamemap.get_actor_at_location(d[0]+self.x,d[1]+self.y)
            if a:
                actors.append(a)
        return actors

    @property
    def room(self):
        for room in self.gamemap.rooms:
            if self.xy in room.tiles:
                return room
        return None


class Actor(Entity):
    def __init__(
        self,
        *,
        x: int = 0,
        y: int = 0,
        char: str = "?",
        color: Tuple[int, int, int] = (255, 255, 255),
        name: str = "<Unnamed>",
        move_speed: int = 1,
        ai_cls: Type[BaseAI],
        render_order: RenderOrder = RenderOrder.ACTOR,
        description: str = None,
        is_boss: bool = False,
        flavor: str = None
    ):
        super().__init__(
            x=x,
            y=y,
            char=char,
            color=color,
            name=name,
            blocks_movement=True,
            render_order=render_order,
            description=description,
            flavor=flavor
        )

        self.inventory = Inventory()
        self.inventory.parent = self
        self.move_speed = move_speed
        self.ai: Optional[BaseAI] = ai_cls(self)
        self.statuses = []
        self.cause_of_death = ''
        self.schedule = {}

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, new_val):
        self._color = new_val

    @property
    def is_alive(self) -> bool:
        """Returns True as long as this actor can perform actions."""
        return bool(self.ai)

    @property
    def scheduled_room(self):
        time_block = 0
        for k in self.schedule.keys():
            if k-1 <= self.engine.hour and k > time_block:
                time_block = k
        time_block = 22 if time_block == 0 else time_block
        return self.schedule[time_block]

    def can_move(self):
        # Make sure player can move, otherwise die    
        for direction in DIRECTIONS:
            tile = self.x + direction[0], self.y + direction[1]
            if ( self.engine.game_map.tile_is_walkable(*tile, self.is_phasing) ) or (self is self.engine.player and self.engine.game_map.tile_is_snakeable(*tile,self.is_phasing)):
                return True

        if (self.engine.player.x, self.engine.player.y) == self.engine.game_map.downstairs_location:
            return True

        return False

    def on_turn(self) -> None:
        for status in self.statuses:
            status.decrement()

    def corpse(self) -> None:
        self.gamemap.bloody_floor(self.x,self.y)

    def die(self) -> None:
        self.ai = None
        if self.engine.player is self:
            death_message = "You died!"
            death_message_color = Color.dark_red
            self.char = "%"
            self.color = Color.corpse
            self.name = f"remains of {self.name}"
            self.render_order = RenderOrder.CORPSE
        else:
            death_message = f"{self.name} is dead!"
            death_message_color = Color.dark_red

            self.engine.history.append(("kill enemy",self.name,self.engine.turn_count))

            if self in self.gamemap.entities:
                self.gamemap.entities.remove(self)

            self.corpse()

        self.engine.message_log.add_message(death_message, death_message_color)

    def take_damage(self, amount: int) -> None:
        self.die()

    def preSpawn(self):
        while self.name == "<Unnamed>" or self.name in [e.name for e in self.gamemap.entities]:
            self.name = random.choice(["Alice","Bob","Charlie","Doug","Emily","Fred","Grish","Hal","Ingus","Josh","Kzyl'xx","Lu","Mo","Ned","Otto","Pete","Quincy","Rod","Stu","Tim","Ulga","Viv","Yan","Zed"])
        if self.char == "?":
            self.char = self.name[0]
        if not self.schedule:
            times = {8,12,18,22}
            schedule = {}
            for time in times:
                location = random.choice(self.gamemap.rooms)
                while location.name == "Main Hall" or location.closet or location in schedule.values():
                    location = random.choice(self.gamemap.rooms)
                schedule[time] = location
            self.schedule = schedule
        self.last_peed = random.choice(range(240))


class Item(Entity):
    """Any letter"""
    def __init__(
        self,
        *,
        x: int = 0,
        y: int = 0,
        color: Tuple[int, int, int] = (255, 255, 255),
        name: str = "<Unnamed>",
        usable: Consumable,
        char: str = '?',
        description: str = None,
        flavor: str = None
    ):
        super().__init__(
            x=x,
            y=y,
            color=color,
            name=name,
            blocks_movement=False,
            render_order=RenderOrder.ITEM,
            description=description,
            flavor=flavor
        )
        self.usable = usable
        self.usable.parent = self
        self._identified = False
        self._color = color

    @property
    def label(self):
        return self.name

    @property
    def identified(self):
        if self.gamemap.game_mode in ['consumable testing']:
            return True
        return [i for i in self.gamemap.item_factories if i.char == self.char][0]._identified

    @property
    def flavor(self):
        return self._flavor if self.identified else "???"

    @identified.setter
    def identified(self, new_val: bool):
        if self._identified:
            return
        factory = [i for i in self.gamemap.item_factories if i.char == self.char][0]
        if factory._identified == True:
            self._identified = True
            return
        factory._identified = self._identified = new_val
        n = 'n' if self.label[0].lower() in ('a','e','i','o','u') else ''
        self.engine.history.append(("identify item", self.label, self.engine.turn_count))
        self.engine.message_log.add_message(f"It was a{n} ?.", Color.offwhite, self.label, self.color)

    @property
    def color(self):
        if not self.identified:
            return Color.unidentified
        return self._color

    @property
    def description(self):
        return self._description

    @color.setter
    def color(self, new_val):
        self._color = new_val

    #remove the item from the game
    def consume(self):
        if self in self.engine.player.inventory.items:
            self.engine.player.inventory.items.remove(self)
