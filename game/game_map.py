from __future__ import annotations

from typing import Iterable, Iterator, Optional, TYPE_CHECKING

import numpy as np  # type: ignore
from tcod.console import Console
from tcod.map import compute_fov
import random

from game import color, tile_types
from game.entity import Actor, Item
from game.actions import ActionWithDirection
from game.render_functions import DIRECTIONS, D_ARROWS
from game.entity_factories import item_factories

if TYPE_CHECKING:
    from game.engine import Engine
    from game.entity import Entity


class GameMap:
    def __init__(
        self, engine: Engine, width: int, height: int, floor_number: int, items: Iterable, entities: Iterable[Entity] = (), vowel = None, decoy = None, game_mode = 'default'
    ):
        self.engine = engine
        self.width, self.height = width, height
        self.entities = set(entities)
        self.tiles = np.full((width, height), fill_value=tile_types.wall, order="F")

        self.visible = np.full(
            (width, height), fill_value=False, order="F"
        )  # Tiles the player can currently see
        self.explored = np.full(
            (width, height), fill_value=False, order="F"
        )  # Tiles the player has seen before
        self.mapped = np.full(
            (width, height), fill_value=False, order="F"
        )
        self.rooms = []

        self.downstairs_location = (0, 0)
        self.floor_number = floor_number
        self.item_factories = items
        self._next_id = 1
        self.game_mode = game_mode

        if self.game_mode == 'overview':
            self.explored = np.full((width,height),fill_value=True,order="F")
            self.visible = np.full((width,height),fill_value=True,order="F")

    def room_at_location(self,x,y):
        for room in self.rooms:
            if any(tile == (x,y) for tile in room.tiles):
                return room.name
        return ''

    @property
    def actors(self) -> Iterable[Actor]:
        """Iterate over this maps living actors."""
        return [
            entity
            for entity in self.entities
            if isinstance(entity, Actor) and entity.is_alive
        ]

    @property
    def gamemap(self) -> GameMap:
        return self

    @property
    def items(self) -> Iterator[Item]:
        yield from (entity for entity in self.entities if isinstance(entity, Item))

    @property
    def next_id(self):
        self._next_id += 1
        return self._next_id

    def bloody_floor(self,x,y):
        if self.tiles[x,y] == tile_types.floor:
            self.tiles[x,y] = tile_types.bloody_floor


    def smellable(self,entity: Entity, super_smell:bool=False):
        dx = entity.x-self.engine.player.x
        dy = entity.y-self.engine.player.y
        distance = max(abs(dx),abs(dy))

        if super_smell:
            return distance <= self.engine.foi_radius
        else:
            return distance <= self.engine.fos_radius


    def make_mapped(self):
        for i,row in enumerate(self.mapped):
            for j, tile in enumerate(row):
                if self.tiles[i,j] not in (tile_types.wall):
                    self.mapped[i,j] = True
                if self.tiles[i,j] == tile_types.down_stairs:
                    self.explored[i,j] = True

    
    def get_blocking_entity_at_location(
        self, location_x: int, location_y: int,
    ) -> Optional[Entity]:
        for entity in self.entities:
            if (
                entity.blocks_movement
                and entity.x == location_x
                and entity.y == location_y
            ):
                return entity

        return None

    def get_actor_at_location(self, x: int, y: int) -> Optional[Actor]:
        for actor in self.actors:
            if actor.x == x and actor.y == y:
                return actor

        return None

    def get_item_at_location(self, x: int, y: int) -> Optional[Item]:
        for item in self.items:
            if item.x == x and item.y == y:
                return item

        return None

    def tile_is_walkable(self, x: int, y: int, phasing: bool = False) -> bool:
        if not self.in_bounds(x, y):
            return False
        if not self.tiles["walkable"][x, y] and not phasing:
            return False
        if self.get_blocking_entity_at_location(x, y):
            return False
        return True

    def in_bounds(self, x: int, y: int) -> bool:
        """Return True if x and y are inside of the bounds of this map."""
        return 0 <= x < self.width and 0 <= y < self.height

    def print_enemy_fom(self, console: Console, entity: Actor):
        if not self.visible[entity.x,entity.y] and not self.smellable(entity, True):
            return

        fom = compute_fov(
            self.tiles["transparent"],
            (entity.x,entity.y),
            radius=entity.move_speed,
            light_walls=False
        )

        for x,row in enumerate(fom):
            for y,cel in enumerate(row):
                if cel and self.visible[x,y] and (x != entity.x or y != entity.y):
                    console.tiles_rgb[x,y]['bg'] = color.highlighted_fom

    def print_enemy_fov(self, console: Console, entity: Actor):
        if (
            entity is self.engine.player or
            not isinstance(entity, Actor) or
            (not self.visible[entity.x,entity.y] and not self.smellable(entity, True))
        ):
            return

        fov = compute_fov(
            self.tiles["transparent"],
            (entity.x, entity.y),
            radius=8,
            light_walls=False
        )

        for x,row in enumerate(fov):
            for y,cel in enumerate(row):
                if cel and self.visible[x,y] and (x != entity.x or y != entity.y):
                    console.tiles_rgb[x,y]['bg'] = color.highlighted_fov
                    console.tiles_rgb[x,y]['fg'] = (40,40,40)
                    #console.print(x=x,y=y,string=" ",bg=color.highlighted_fov)


    def print_actor_tile(self,actor,location,console):
        fg = actor.color
        bg = None
        string = actor.char
        x,y = location

        if self.visible[actor.x,actor.y]:
            pass

        elif self.smellable(actor, True):
            bg=color.grey

        elif self.smellable(actor):
            string = '?'
            fg = color.yellow
            bg = color.grey

        else:
            return False

        console.print(x=x,y=y,string=string,fg=fg,bg=bg)
        return True

    def print_item_tile(self,item,location,console):
        fg = item.color
        x,y = location

        if item is self.engine.player:
            if not self.tiles['walkable'][item.x,item.y]:
                fg = color.purple
            elif self.visible[item.x,item.y]:
                fg = item.color
            else:
                fg = color.player_dark
        elif not self.visible[item.x,item.y] and self.explored[item.x,item.y]:
            fg = tuple(i//2 for i in fg)
        elif not self.visible[item.x,item.y]:
            return False

        console.print(x,y,item.char,fg=fg)
        return True

    def print_tile(self,entity,location,console):
        if isinstance(entity, Actor) and entity is not self.engine.player:
            return self.print_actor_tile(entity,location,console)
        else:
            return self.print_item_tile(entity,location,console)


    def render(self, console: Console) -> None:
        """
        Renders the map.
 
        If a tile is in the "visible" array, then draw it with the "light" colors.
        If it isn't, but it's in the "explored" array, then draw it with the "dark" colors.
        Otherwise, the default is "SHROUD".
        """
        console.tiles_rgb[0 : self.width, 0 : self.height] = np.select(
            condlist=[self.visible, self.explored, self.mapped],
            choicelist=[self.tiles["light"], self.tiles["dark"], tile_types.MAPPED],
            default=tile_types.SHROUD,
            #default=self.tiles["dark"]
        )

        entities_sorted_for_rendering = sorted(
            self.entities, key=lambda x: x.render_order.value
        )         

        # display entities
        for entity in entities_sorted_for_rendering:
            if isinstance(entity,Actor) and entity is not self.engine.player:
                self.print_actor_tile(entity,entity.xy,console)
            elif entity is self.engine.player:
                continue
            else:
                self.print_item_tile(entity,entity.xy,console) # player counts as an item

        self.print_item_tile(self.engine.player,self.engine.player.xy,console)


class GameWorld:
    """
    Holds the settings for the GameMap, and generates new maps when moving down the stairs.
    """

    def __init__(
        self,
        *,
        engine: Engine,
        map_width: int,
        map_height: int,
        current_floor: int=0,
        game_mode: str
    ):
        self.game_mode = game_mode
        self.engine = engine
        self.map_width = map_width
        self.map_height = map_height
        self.current_floor = current_floor
        self.items = item_factories

    def generate_floor(self) -> None:
        from game.procgen import generate_dungeon

        self.current_floor += 1

        if self.game_mode in ['consumable testing']:
            self.engine.game_map = generate_consumable_testing_ground(engine=self.engine, items=self.items)
            return

        self.engine.game_map = generate_dungeon(
            map_width=self.map_width,
            map_height=self.map_height,
            engine=self.engine,
            floor_number=self.current_floor,
            items=self.items,
            game_mode=self.game_mode
        )