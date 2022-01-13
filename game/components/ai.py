from __future__ import annotations

import random
from typing import List, Tuple, TYPE_CHECKING
from typing import List, Optional, Tuple, TYPE_CHECKING

import numpy as np  # type: ignore
import tcod

from game.exceptions import Impossible
from game.actions import Action, BumpAction, MovementAction, WaitAction, TalkAction, TazeAction
from game import color
from game.render_functions import DIRECTIONS
from game.components.status_effect import BeingEaten, Tazed

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

    def perform(self,intent=None) -> None:
        self._intent = intent or []

        ai = self.override or self.resolve or self
        if ai != self:
            self.entity.ai = ai
            return ai.perform(self._intent)

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
        self.path = self.get_path_to(*tile)

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

    def __init__(self, entity: Actor, parent=None):
        super().__init__(entity)
        self.path = None
        self.move_speed = entity.move_speed
        self.target_tile = None
        self.parent = parent
        self.suspicions = {}
        self.found = []
        self.just_tazed = None

    @property
    def description(self):
        return "content"

    @property
    def missing_persons(self):
        if self.entity.xy not in self.entity.scheduled_room.tiles:
            return []

        mp = []
        for e in self.entity.gamemap.entities:
            if not e.changeling_form and e.scheduled_room is self.entity.scheduled_room and e.room is not self.entity.scheduled_room and not self.entity.fov[e.x,e.y]:
                p = self.engine.player
                if p.name == e.name and self.entity.fov[p.x,p.y]:
                    continue
                if e.name in self.engine.investigations:
                    continue
                if e.name in self.engine.investigators:
                    continue
                mp.append(e)
        return mp

    @property
    def fov_actors(self):
        return [e for e in self.entity.gamemap.entities if self.entity.fov[e.x,e.y]]

    # AI PRIORITIES ===========================

    @property
    def is_being_eaten(self):
        return any(isinstance(i,BeingEaten) for i in self.entity.statuses)

    @property
    def needs_to_investigate(self):
        for n in self.suspicions.keys():
            if self.suspicions[n] > 100 and n not in self.engine.investigations:
                return n
        return False

    @property
    def has_to_pee(self):
        return self.engine.turn_count - self.entity.last_peed > 240

    @property
    def override(self):
        if self.entity.tazed:
            return TazedNPC(self.entity,self)
        if self.is_being_eaten:
            return BeingEatenNPC(self.entity,self)
        if self.needs_to_investigate:
            return InvestigationNPC(self.entity,self,self.needs_to_investigate)
        if self.has_to_pee:
            return PeeNPC(self.entity,self)

    @property
    def resolve(self):
        return self


    # shuttleless version of suspicion meter

    # seeing your true form:
        # [i]Changeling spotted in [room]!!
        # x starts running!
        # everyone rushes to that room
        # if sighting confirmed, evacuation announcement
        # if you're the person who cried, [i]False alarm folks! Let my nerves get the better of me!
        # otherwise an investigation to find them begins

    # ===== 
    # evacuation behavior
        # suspicion > 20 = flee 
        # "Stay away from me until we can clear the bioscanner!"
        # everyone tazes each other on sight

    # test
        # tazing NPCs stuns them for a turn (maybe give player taze action?) and they do the voice

    def decide(self):
        # clear someone's name if you tazed em and nothing else is going on
        self.taze_check()

        # if you see something say something
        for a in self.fov_actors:
            if a.name in self.suspicions or a.name in self.engine.investigations:
                if a.name in self.suspicions:
                    del self.suspicions[a.name]

                if a.name not in self.found:
                    i = '[i]' if a.name in self.engine.investigations else ''
                    r = f" in the {a.room.name}" if a.name in self.engine.investigations else ''
                    self._intent.append(TalkAction(self.entity,0,0,f"{i}I found {a.name}{r}!"))
                    self.found.append(a.name)

        # lose sight of people
        for i,name in enumerate(self.found):
            if name not in [a.name for a in self.fov_actors]:
                self.found.pop(i)

        # if you see a taze on sight individual, get em
        for a in self.engine.investigations:
            for b in self.fov_actors:
                if a == b.name:
                    return self.taze(b.xy)

        # add missing persons to suspicion tally
        for p in self.missing_persons:
            if p.name in self.suspicions:
                if p.name in self.engine.investigations:
                    del self.suspicions[p.name]
                else:
                    self.suspicions[p.name] += 1
            else:
                self.suspicions[p.name] = 1

        # decide on my target
        if self.entity.room is not self.entity.scheduled_room and not self.target_tile:
            self.target_tile = random.choice(self.entity.scheduled_room.inner)

        self.mosey()

    # ========================================

    def taze_check(self):
        if self.just_tazed:
            if self.just_tazed.name in self.engine.investigations:
                i = self.engine.investigations.index(self.just_tazed.name)
                self.engine.investigations.pop(i)
                self.engine.investigators.pop(i)
                self._intent.append(TalkAction(self.entity,self.entity.x,self.entity.y,f"[i]{self.just_tazed.name} tazed and cleared of suspicion!"))
            self.just_tazed = None

    def taze(self,target_tile):
        if [e for e in self.engine.game_map.entities if e.xy == target_tile][0].tazed:
            if self.entity.distance(*target_tile) < 2:
                self._intent.append(BumpAction(self.entity,self.entity.x-target_tile[0],self.entity.y-target_tile[1]))

        elif self.entity.distance(*target_tile) < 2:
            self._intent.append(TazeAction(self.entity,target_tile[0]-self.entity.x,target_tile[1]-self.entity.y))
        
        else:
            self.goto(target_tile)


    def get_voice_lines(self,target):
        lines = []

        if not target:
            lines.append("Ha, I just had a great idea!")

        if self.target_tile and self.entity.room is not self.entity.scheduled_room:
            room = [room for room in self.entity.gamemap.rooms if self.target_tile in room.inner][0]
            lines.append(f"Excuse me, I've got to get to the {room.name}.")
        elif self.entity.room is self.entity.scheduled_room:
            lines.append(f"*whistles*")

        if self.entity.room is not self.entity.scheduled_room and target:
            lines.append(f"Hello there, {target.name}!")
            lines.append(f"{target.name}! Good to see you.")

        for p in self.missing_persons:
            lines.append(f"I wonder where {p.name} is.")
            lines.append(f"{p.name} is usually here this time of day...")

        for n in self.suspicions.keys():
            amt = self.suspicions[n]
            lines.append(f"My suspicion of {n} is at {amt}.")
            if amt > 100:
                lines.append(f"[i]My suspicion of {n} is at {amt}.")


        return lines

    def mosey(self):
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


class InvestigationNPC(DefaultNPC):
    def __init__(self,entity,parent,subject):
        super().__init__(entity,parent)
        self.subject = subject
        self.has_announced = False
        self.subject_cleared = False
        self.investigation_started = self.engine.turn_count
        self.has_approached = False
        self.subject_last_spotted = None

        self.engine.investigations.append(self.subject)
        self.engine.investigators.append(self.entity.name)

        del parent.suspicions[subject]

    @property
    def description(self):
        return "investigating"

    @property
    def needs_to_investigate(self):
        return False

    @property
    def has_to_pee(self):
        return False

    @property
    def resolve(self):
        if self.subject not in self.engine.investigations:
            return self.parent

        if self.subject_cleared:
            announcement = f"[i]{self.subject} has been found and their humanity verified. Stay safe everyone!"
            self._intent.append(TalkAction(self.entity,self.entity.x,self.entity.y,announcement))
            self.engine.investigations.remove(self.subject)
            self.engine.investigators.remove(self.entity.name)
            return self.parent

        investigation_duration = self.engine.turn_count - self.investigation_started

        if investigation_duration > 480:
            announcement = f"[i]After a full day, {self.subject} has eluded me. Begin evacuation procedure. Trust no one."
            self._intent.append(TalkAction(self.entity,self.entity.x,self.entity.y,announcement))
            self.engine.investigations.remove(self.subject)
            self.engine.investigators.remove(self.entity.name)
            self.engine.evacuation_mode = True
            return self.parent
        
        return self

    def get_voice_lines(self,target):
        return [
            f"Do let me know if you see {self.subject}!",
            f"If I don't find {self.subject} quick, this whole place'll be upended."
        ]

    def decide(self):
        # announce your investigation when it starts
        if not self.has_announced:
            announcement = f"[i]{self.subject} is hereby under investigation. If seen, taze them on sight!"
            self._intent.append(TalkAction(self.entity,self.entity.x,self.entity.y,announcement))
            self.has_announced = True

        self.taze_check()

        # if you've followed them to where you last saw them, stop doing that
        if self.entity.xy == self.subject_last_spotted:
            self.subject_last_spotted = None

        if self.entity.xy == self.target_tile:
            self.target_tile = None

        # if you can see them, get em
        if self.subject in [a.name for a in self.fov_actors]:
            self.subject_last_spotted = [a for a in self.fov_actors if a.name == self.subject][0].xy
            if not self.has_approached:
                self._intent.append(TalkAction(self.entity,self.entity.x,self.entity.y,f"{self.subject}! Hold still for a second, let me verify you!"))
                self.has_approached = True

            return self.taze(self.subject_last_spotted)

        # if you can't, go where you last did
        if self.subject_last_spotted:
            return self.goto(self.subject_last_spotted)

        # if you see another taze on sight individual, get em
        for a in self.engine.investigations:
            for b in self.fov_actors:
                if a == b.name:
                    return self.taze(b.xy)
        
        # failing that, pick a room
        if not self.target_tile:
            room = random.choice(self.engine.game_map.rooms)
            self.target_tile = random.choice(room.inner)

        # and go there
        if self.target_tile:
            return self.goto(self.target_tile)



class Changeling(DefaultNPC):
    @property
    def description(self):
        return "hungry"

    @property
    def missing_persons(self):
        return []

    def get_voice_lines(self):
        if not self.changeling_form:
            return super().get_voice_lines()
        else:
            return ["Rlyxhheehhhxxxsss","SSSLlslllLLlLlurRRRRP", "hhhh", "*schlorp*", "..."]

    @property
    def needs_to_investigate(self):
        return False

    @property
    def has_to_pee(self):
        return False

    @property
    def override(self):
        return

    @property
    def resolve(self):
        return

    def decide(self):
        return


class BeingEatenNPC(DefaultNPC):
    chance_to_chat=1

    @property
    def description(self):
        return "struggling"

    def get_voice_lines(self,target=None):
        return ["Mmffhh!!!","Hrrmlllp!","*muffled sobs*"]

    @property
    def is_being_eaten(self):
        return False

    @property
    def needs_to_investigate(self):
        return False

    @property
    def panicking(self):
        return False

    @property
    def has_to_pee(self):
        return False

    @property
    def resolve(self):
        if not any(isinstance(i,BeingEaten) for i in self.entity.statuses):
            return self.parent

    def decide(self):
        self._intent.append(TalkAction(self.entity,self.entity.x,self.entity.y))
        self._intent.append(WaitAction(self.entity))


class TazedNPC(DefaultNPC):
    chance_to_chat=1

    @property
    def description(self):
        return "stunned"

    def get_voice_lines(self,target=None):
        return ["Ow, stop that!", "Ouch!", "Back off!"]

    @property
    def is_being_eaten(self):
        return False

    @property
    def needs_to_investigate(self):
        return False

    @property
    def panicking(self):
        return False

    @property
    def has_to_pee(self):
        return False

    @property
    def resolve(self):
        if not any(isinstance(i,Tazed) for i in self.entity.statuses):
            return self.parent

    def decide(self):
        self._intent.append(TalkAction(self.entity,self.entity.x,self.entity.y))
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

    @property
    def has_to_pee(self):
        return False

    @property
    def resolve(self):
        if self.pee_duration < 1:
            return self.parent

    def decide(self):
        # pick the right toilet if you aren't there yet
        if self.entity.xy != self.target_tile:
            self.target_tile = self.pick_toilet()

        # keep peein if you are
        if self.entity.xy == self.target_tile:

            # log it if you're finishing up
            self.pee_duration -= 1
            if self.pee_duration < 1:
                self.entity.last_peed = self.engine.turn_count

            for tile in self.entity.room.inner:
                if any(entity.xy == tile and entity is not self.entity for entity in self.entity.gamemap.entities):
                    self._intent.append(TalkAction(self.entity,self.entity.x,self.entity.y))
                    break
            self._intent.append(WaitAction(self.entity))
            return

        # otherwise get there
        self.mosey()
        

    def pick_toilet(self):
        toilets = [room for room in self.entity.gamemap.rooms if room.closet]
        path = None
        for toilet in toilets:
            def occupied():
                for tile in toilet.inner:
                    if any(entity.xy == tile and not entity.changeling_form and entity is not self.entity for entity in self.entity.gamemap.entities):
                        return True
            if occupied():
                continue
            for tile in toilet.inner:
                this_path = self.get_path_to(*tile)
                if this_path and (not path or len(this_path) < len(path[1])):
                    path = (tile,this_path)

        if path:
            return path[0]

