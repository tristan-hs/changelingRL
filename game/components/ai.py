from __future__ import annotations

import random
from typing import List, Tuple, TYPE_CHECKING
from typing import List, Optional, Tuple, TYPE_CHECKING

import numpy as np  # type: ignore
import tcod

from game.exceptions import Impossible
from game.actions import Action, BumpAction, MeleeAction, MovementAction, WaitAction, TalkAction
from game import color
from game.render_functions import DIRECTIONS

if TYPE_CHECKING:
    from game.entity import Actor
    from game.action import Action

class BaseAI(Action):

    _intent = None

    @property
    def intent(self) -> Optional[List[Action]]:
        if self._intent:
            return self._intent
        self.decide()
        return self._intent

    @property
    def fov(self):
        return tcod.map.compute_fov(
            self.engine.game_map.tiles["transparent"],
            (self.entity.x, self.entity.y),
            radius=8,
        )

    def clear_intent(self):
        self._intent = None

    def decide(self) -> Optional[Action]:
        raise NotImplementedError()

    def perform(self) -> None:
        self._intent = []

        ai = self.set_goals()
        if ai != self:
            self.entity.ai = ai
            return ai.perform()

        self.decide()
        for i in self.intent:
            try:
                i.perform()
                if i.meleed:
                    break
            except Impossible:
                break
        self._intent = None

    def get_path_to(self, dest_x: int, dest_y: int, path_cost:int = 10, walkable=True) -> List[Tuple[int, int]]:
        """Compute and return a path to the target position.

        If there is no valid path then returns an empty list.
        """
        # Copy the walkable array.

        gm = self.entity.gamemap
        tiles = gm.tiles["walkable"] if walkable else np.full((gm.width,gm.height),fill_value=1,order="F")
        cost = np.array(tiles, dtype=np.int8)

        for entity in gm.entities:
            # Check that an enitiy blocks movement and the cost isn't zero (blocking.)
            if entity.blocks_movement and cost[entity.x, entity.y] and (entity.x != dest_x or entity.y != dest_y):
                # Add to the cost of a blocked position.
                # A lower number means more enemies will crowd behind each other in
                # hallways.  A higher number means enemies will take longer paths in
                # order to surround the player.
                cost[entity.x, entity.y] += path_cost

        # Create a graph from the cost array and pass that graph to a new pathfinder.
        graph = tcod.path.SimpleGraph(cost=cost, cardinal=3, diagonal=4)
        pathfinder = tcod.path.Pathfinder(graph)

        pathfinder.add_root((self.entity.x, self.entity.y))  # Start position.

        # Compute the path to the destination and remove the starting point.
        path: List[List[int]] = pathfinder.path_to((dest_x, dest_y))[1:].tolist()

        # Convert from List[List[int]] to List[Tuple[int, int]].
        return [(index[0], index[1]) for index in path]

    def goto(self,tile):
        self.path = self.get_path_to(*self.target_tile)

        if self.path:
            next_move = self.path[0:self.move_speed]
            fx, fy = self.entity.x, self.entity.y
            for m in next_move:
                if not self.engine.game_map.tile_is_walkable(*m):
                    break
                dx = m[0]-fx
                dy = m[1]-fy
                self._intent.append(BumpAction(self.entity, dx, dy))
                fx += dx
                fy += dy



class DefaultNPC(BaseAI):
    chance_to_chat = 0.2

    def __init__(self, entity: Actor):
        super().__init__(entity)
        self.path = None
        self.move_speed = entity.move_speed
        self.target_tile = None

    @property
    def description(self):
        return "content"

    @property
    def missing_persons(self):
        if self.entity.xy not in self.entity.scheduled_room.tiles:
            return []

        mp = []
        for e in self.entity.gamemap.entities:
            if e.scheduled_room is self.entity.scheduled_room and e.room is not self.entity.scheduled_room and not self.entity.fov[e.x,e.y]:
                mp.append(e)
        return mp

    def get_voice_lines(self,target):
        lines = []

        if not target:
            lines.append("Ha, I just had a great idea!")

        if self.target_tile and self.entity.room is not self.entity.scheduled_room:
            room = [room for room in self.entity.gamemap.rooms if self.target_tile in room.inner][0]
            lines.append(f"Excuse me, I've got to get to the {room.name}.")
        elif self.entity.room is self.entity.scheduled_room:
            lines.append(f"Work, work, work, keeps my hands busy.")

        if self.entity.room is not self.entity.scheduled_room and target:
            lines.append(f"Hello there, {target.name}!")
            lines.append(f"{target.name}! Good to see you.")

        for p in self.missing_persons:
            lines.append(f"I wonder where {p.name} is.")
            lines.append(f"{p.name} is usually here this time of day...")

        return lines

    def set_goals(self):
        # make sure I'm in the right mode
        if self.engine.turn_count - self.entity.last_peed > 240:
            return PeeNPC(self.entity)

        # decide on my target
        if self.entity.room is not self.entity.scheduled_room and not self.target_tile:
            self.target_tile = random.choice(self.entity.scheduled_room.inner)

        return self

    def decide(self):
        # random chance to talk to whoever's next to me
        adjacent_actors = self.entity.get_adjacent_actors()
        if len(adjacent_actors) > 0 and random.random() < self.chance_to_chat:
            a = random.choice(adjacent_actors)
            d = (a.x-self.entity.x,a.y-self.entity.y)
            self._intent.append(BumpAction(self.entity, d[0], d[1]))
            return

        # random chance to just muse as you go
        if random.random() < self.chance_to_chat and random.random() < self.chance_to_chat:
            self._intent.append(TalkAction(self.entity,self.entity.x,self.entity.y))

        # try to get where I'm supposed to be
        if self.target_tile:
            if self.entity.xy == self.target_tile:
                self.target_tile = None
            else:
                self.goto(self.target_tile)
                if len(self._intent) > 0:
                    return

        # wander my assigned area
        if random.random() > 0.5:
            dx,dy = random.choice(DIRECTIONS)
            self._intent.append(BumpAction(self.entity,dx,dy))
            return

        # chill
        self._intent.append(WaitAction(self.entity))

class PeeNPC(DefaultNPC):
    chance_to_chat = 0.1
    pee_duration = 10

    @property
    def description(self):
        return "needs to pee"

    def get_voice_lines(self, target=None):
        lines = []
        if self.entity.xy == self.target_tile:
            lines = ["Get out of here!", "Occupied!", "Some privacy please!"]
        elif self.target_tile:
            lines.append(f"I've gotta see a man about a horse.")
        elif self.entity.room is self.entity.scheduled_room:
            lines.append(f"Think I'll take a break soon")

        return lines + super().get_voice_lines(target)


    def set_goals(self):
        if self.entity.xy == self.target_tile:
            self.pee_duration -= 1
            if self.pee_duration < 1:
                self.entity.last_peed = self.engine.turn_count
                return DefaultNPC(self.entity)
        else:
            self.target_tile = self.pick_toilet()

        return self

    def decide(self):
        # wait if you're in the right place
        if self.entity.xy == self.target_tile:
            for tile in self.entity.room.inner:
                if any(entity.xy == tile and entity is not self.entity for entity in self.entity.gamemap.entities):
                    self._intent.append(TalkAction(self.entity,self.entity.x,self.entity.y))
                    break
            self._intent.append(WaitAction(self.entity))
            return
        # otherwise default stuff will get you there
        super().decide()
        

    def pick_toilet(self):
        toilets = [room for room in self.entity.gamemap.rooms if room.closet]
        path = None
        for toilet in toilets:
            def occupied():
                for tile in toilet.inner:
                    if any(entity.xy == tile for entity in self.entity.gamemap.entities):
                        return True
            if occupied():
                continue
            for tile in toilet.inner:
                this_path = self.get_path_to(*tile)
                if this_path and (not path or len(this_path) < len(path[1])):
                    path = (tile,this_path)

        if path:
            return path[0]


class HostileEnemy(BaseAI):

    def __init__(self, entity: Actor,):
        super().__init__(entity)
        self.path: List[Tuple[int, int]] = None
        self.move_speed = entity.move_speed
        self.last_target = None

    @property
    def description(self):
        return "hostile" if self.last_target else "asleep"

    def distance_to(self, tx, ty):
        dx = tx-self.entity.x
        dy = ty-self.entity.y
        return max(abs(dx),abs(dy))

    def pick_target(self):
        fov = tcod.map.compute_fov(
            self.engine.game_map.tiles["transparent"],
            (self.entity.x, self.entity.y),
            radius=8,
        )

        # pick the first thing in fov that you can path to:
            # a decoy
            # the nearest of the player or its parts
                # if you are seeing the player after not being in attack mode, send the notice message
            # the last place you saw a player or its parts

        # set last_target to whatever you pick

        target = None

        d_to_t = 0
        for entity in [self.engine.player]:
            if fov[entity.x,entity.y]:
                d = len(self.get_path_to(*entity.xy))
                if d and (not d_to_t or d_to_t > d):
                    d_to_t = d
                    target = entity
        if target:
            if not self.last_target:
                self.engine.message_log.add_message(f"The ? spotted you!", color.offwhite, self.entity.name, self.entity.color)
            self.last_target = target.xy
            return (target,d_to_t,target.xy)

        if self.last_target:
            d = len(self.get_path_to(*self.last_target))
            if d:
                return (None, d, self.last_target)

        return (None, None, None)


    def decide(self) -> Optional[Action]:
        self._intent = []

        target, distance, xy = self.pick_target()
        x, y = self.entity.xy

        if not xy:
            self._intent.append(WaitAction(self.entity))
            return

        if distance == 1:
            self._intent.append(BumpAction(self.entity, xy[0]-x, xy[1]-y))
            return
        
        self.path = self.get_path_to(xy[0], xy[1])

        if self.path:
            next_move = self.path[0:self.move_speed]
            fx, fy = x, y
            for m in next_move:
                # only intend to move into non-walkables as an attack on a known target
                if not self.engine.game_map.tile_is_walkable(*m) and (not target or m != target.xy):
                    break
                dx = m[0]-fx
                dy = m[1]-fy
                self._intent.append(BumpAction(self.entity, dx, dy))
                fx += dx
                fy += dy
            if len(self._intent) > 0:
                return

        self._intent.append(WaitAction(self.entity))


class Statue(BaseAI):
    description = "docile"

    def decide(self) -> Optional[Action]:
        self._intent = [WaitAction(self.entity)]


class ConfusedEnemy(BaseAI):
    description = "confused"
    """
    A confused enemy will stumble around aimlessly for a given number of turns, then revert back to its previous AI.
    If an actor occupies a tile it is randomly moving into, it will attack.
    """

    def __init__(
        self, entity: Actor,
    ):
        super().__init__(entity)
        self.move_speed = entity.move_speed

    def decide(self) -> Optional[Action]:
        self._intent = []

        for i in range(self.move_speed):
            # Pick a random direction
            direction_x, direction_y = random.choice(
                [
                    (-1, -1),  # Northwest
                    (0, -1),  # North
                    (1, -1),  # Northeast
                    (-1, 0),  # West
                    (1, 0),  # East
                    (-1, 1),  # Southwest
                    (0, 1),  # South
                    (1, 1),  # Southeast
                ]
            )
            self._intent.append(BumpAction(self.entity, direction_x, direction_y))

    def perform(self) -> None:
        super().perform()
