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
    short_description = ''

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

    def runfrom(self,tile):
        dx,dy = (tile[0] - self.entity.x, tile[1] - self.entity.y)

        if dx > 0:
            dx = -1
        elif dx < 0:
            dx = 1

        if dy > 0:
            dy = -1
        elif dy < 0:
            dy = 1

        self._intent.append(BumpAction(self.entity,dx,dy))


class DefaultNPC(BaseAI):
    chance_to_chat = 0.2

    description = "content"
    short_description = "☺"

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
        return [e for e in self.engine.game_map.entities if self.fov[e.x,e.y] and e is not self.entity]

    # AI PRIORITIES ===========================

    @property
    def is_being_eaten(self):
        return any(isinstance(i,BeingEaten) for i in self.entity.statuses)

    @property
    def sees_a_changeling(self):
        return any(i.changeling_form or i.name in self.entity.known_changelings for i in self.fov_actors)

    @property
    def heard_a_sighting(self):
        return len(self.engine.sightings)

    @property
    def needs_to_evacuate(self):
        return self.engine.evacuation_mode

    @property
    def needs_to_investigate(self):
        for n in self.suspicions.keys():
            if self.suspicions[n] > 100 and n not in self.engine.investigations:
                return n
        for a in self.fov_actors:
            if a.is_dismantling and a not in self.engine.investigations:
                return a.name
        return False

    @property
    def has_to_pee(self):
        return self.engine.turn_count - self.entity.last_peed > 240

    @property
    def tazed(self):
        return self.entity.tazed

    @property
    def override(self):
        if self.tazed:
            return TazedNPC(self.entity,self)
        if self.is_being_eaten:
            return BeingEatenNPC(self.entity,self)
        if self.sees_a_changeling:
            return FightOrFleeNPC(self.entity,self)
        if self.needs_to_evacuate:
            return EvacuationNPC(self.entity,self)
        if self.heard_a_sighting:
            return InvestigateSightingNPC(self.entity,self)
        if self.needs_to_investigate:
            return InvestigationNPC(self.entity,self,self.needs_to_investigate)
        if self.has_to_pee:
            return PeeNPC(self.entity,self)

    @property
    def resolve(self):
        return self

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
                    if self.suspicions[p.name] == 50:
                        self._intent.append(TalkAction(self.entity,0,0,random.choice([
                            f"[i]{p.name}, you're missed in the {self.entity.room.name}. Please report in.",
                            f"[i]If anybody sees {p.name}, tell them to get to the {self.entity.room.name}, stat!",
                            f"[i]{p.name} to the {self.entity.room.name} please. Double time."
                        ])))
            else:
                self.suspicions[p.name] = 1

        # decide on my target
        if self.entity.room is not self.entity.scheduled_room and not self.target_tile:
            self.target_tile = random.choice(self.entity.scheduled_room.inner) if self.entity.scheduled_room is not self.engine.game_map.shuttle else random.choice(self.engine.game_map.shuttle.lobby)

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
            lines.append(random.choice([
                "Ha, I just had a great idea!",
                "Hmm..."
            ]))

        if self.target_tile and self.entity.room is not self.entity.scheduled_room:
            room = [room for room in self.entity.gamemap.rooms if self.target_tile in room.inner][0]
            lines.append(random.choice([
                f"Excuse me, I've got to get to the {room.name}.",
                "Gotta go!",
                f"The {room.name} isn't gonna {room.name} itself!"
            ]))

        elif self.entity.room is self.entity.scheduled_room:
            lines.append(random.choice([
                f"*whistles*",
                "*human noises*"
            ]))

        if self.entity.room is not self.entity.scheduled_room and target:
            lines.append(f"Hello there, {target.name}!")
            lines.append(f"{target.name}! Good to see you.")

        for p in self.missing_persons:
            if p.name in self.suspicions and self.suspicions[p.name] > 25:
                lines.append(f"I wonder where {p.name} is.")
                lines.append(f"{p.name} is usually here this time of day...")

        for n in self.suspicions.keys():
            if self.suspicions[n] > 50:
                lines.append(f"{n} has been acting strange lately.")
                lines.append(f"Wonder what {n} has been up to. Uncool to worry everyone like that.")
                lines.append(f"Imagine just not showing up for your shift.")

        for i in self.engine.investigations:
            lines.append(f"I hope {i} is okay...")
            lines.append(f"Jeez, if {i} doesn't turn up soon we'll have to evacuate.")
            lines.append(f"{i} had better have a good explanation for disappearing.")

        for i in self.engine.investigators:
            lines.append(f"I wonder if {i} will find what they're looking for.")
            lines.append(f"I saw {i} wandering around. Looking for someone, I guess.")
            lines.append(f"{i}'s on the move. Guess someone went missing.")

        if len(self.engine.investigations) > 1:
            keyholder = [a for a in self.engine.game_map.actors if a.is_keyholder and a is not self.engine.player]
            if len(keyholder):
                kh = keyholder[0].name
                lines.append(f"With all these disappearances, {kh} should just start the evacuation.")
                lines.append(f"I hope {kh} is staying safe. Things are getting weird.")
            lines.append("Something really strange is going on.")
            lines.append("What a mess. If the bioscanner's intact, we should just leave.")


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
    description = "investigating"
    short_description = "Θ"
    needs_to_investigate = False
    has_to_pee = False

    def __init__(self,entity,parent,subject):
        super().__init__(entity,parent)
        self.subject = subject
        self.investigation_started = self.engine.turn_count

        self.engine.investigations.append(self.subject)
        self.engine.investigators.append(self.entity.name)

        self.has_announced = False
        self.subject_cleared = False
        self.has_approached = False
        self.subject_last_spotted = None

        if subject in parent.suspicions:
            del parent.suspicions[subject]

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
            announcement = random.choice([
                f"[i]After a full day, {self.subject} has eluded me. Begin evacuation procedure. Trust no one.",
                f"[i]I'm afraid my investigation has been unsuccessful. Please make your way to the Shuttle for evacution.",
                f"[i]{self.subject} has been missing for 24 hours. Sorry everyone. It's time to go home."
            ])
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
            announcement = random.choice([
                f"[i]{self.subject} is hereby under investigation. If seen, taze them on sight!",
                f"[i]Warning all personnel: {self.subject} is missing. Have tazers ready in case they turn up.",
                f"[i]Changeling procedures everyone. {self.subject} is to be tazed on sight in case of infection."
            ])
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
                vl = random.choice([
                    f"{self.subject}! Hold still for a second, let me verify you!",
                    f"Sorry, {self.subject}, but it's procedure. I'm gonna have to taze you.",
                    f"Hey, wait! {self.subject}! Come here!"
                ])
                self._intent.append(TalkAction(self.entity,self.entity.x,self.entity.y,vl))
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
            self.target_tile = random.choice(room.inner) if room is not self.engine.game_map.shuttle else random.choice(room.lobby)

        # and go there
        if self.target_tile:
            return self.goto(self.target_tile)



class Changeling(DefaultNPC):
    description = "hungry"
    short_description = '☻'
    missing_persons = []
    tazed = False
    is_being_eaten = False
    sees_a_changeling = False
    heard_a_sighting = False
    needs_to_evacuate = False
    needs_to_investigate = False
    has_to_pee = False
    override = None
    resolve = None

    def get_voice_lines(self):
        if not self.changeling_form:
            return super().get_voice_lines()
        else:
            return ["Rlyxhheehhhxxxsss","SSSLlslllLLlLlurRRRRP", "hhhh", "*schlorp*", "..."]

    def decide(self):
        return


class BeingEatenNPC(DefaultNPC):
    chance_to_chat=1
    is_being_eaten = False
    sees_a_changeling = False
    heard_a_sighting = False
    needs_to_evacuate = False
    needs_to_investigate = False
    has_to_pee = False
    description = "struggling"
    short_description = "D:"

    def get_voice_lines(self,target=None):
        return ["Mmffhh!!!","Hrrmlllp!","*muffled sobs*","...gkh!","*choking*","*gurgling*","KKhhhhh...."]

    @property
    def resolve(self):
        if not any(isinstance(i,BeingEaten) for i in self.entity.statuses):
            return self.parent

    def decide(self):
        self._intent.append(TalkAction(self.entity,self.entity.x,self.entity.y))
        self._intent.append(WaitAction(self.entity))


class TazedNPC(DefaultNPC):
    chance_to_chat=1
    tazed = False
    is_being_eaten = False
    sees_a_changeling = False
    heard_a_sighting = False
    needs_to_evacuate = False
    needs_to_investigate = False
    has_to_pee = False
    description = "stunned"
    short_description = "*_*"

    def get_voice_lines(self,target=None):
        return ["Ow, stop that!", "Ouch!", "Back off!"]

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
    description = "needs to pee"
    short_description = "☺'"
    has_to_pee = False

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


class FightOrFleeNPC(DefaultNPC):
    chance_to_chat = 0
    sees_a_changeling = False
    heard_a_sighting = False
    needs_to_evacuate = False
    needs_to_investigate = False
    has_to_pee = False
    description = "fight or flight"
    short_description = '!'

    def __init__(self,entity,parent):
        super().__init__(entity,parent)
        self.has_announced = False


    @property
    def resolve(self):
        if not any(a.changeling_form or a.name in self.entity.known_changelings for a in self.fov_actors):
            return self.parent

    def decide(self):
        # if this is your first turn in fight or flight, either announce or confirm a sighting
        if not self.has_announced:
            sightings = [s for s in self.engine.sightings if s[0] == self.engine.player.room]
            if len(sightings) and sightings[0][1] != self.entity.name:
                announcement = random.choice([
                    f"[i]Confirming changeling sighting in {sightings[0][0].name}! Evacuate immediately!",
                    f"[i]Yep, that's a changeling! Keyholder to Shuttle, now!!",
                    f"[i]Changeling confirmed in {sightings[0][0].name}! Mother of god, get everyone OUT!"
                ])
                self.engine.evacuation_mode = True
                self.engine.sightings = []
                self._intent.append(TalkAction(self.entity,self.entity.x,self.entity.y,announcement))
            else:
                if not any(s[0] == self.engine.player.room and s[1] == self.entity.name for s in sightings):
                    announcement = random.choice([
                        f"[i]Changeling sighted in {self.engine.player.room.name}! Help!",
                        f"[i]HELP! IT'S ONE OF THOSE THINGS! COME TO {self.engine.player.room.name}!",
                        f"[i]S-someone come to {self.engine.player.room.name}! It's grotesque!"
                    ])
                    self.engine.sightings.append((self.engine.player.room,self.entity.name,False))
                else:
                    announcement = random.choice(["*screams*", "What is that thing?!", "BACK, DEMON!!", "Is it real!!?"])
                self._intent.append(TalkAction(self.entity,self.entity.x,self.entity.y,announcement))
            self.has_announced = True

        # if it's next to you, taze it
        if self.entity in self.engine.player.get_adjacent_actors():
            self._intent.append(TazeAction(self.entity,self.engine.player.x-self.entity.x,self.engine.player.y-self.entity.y))
            return

        # if there are allies in sight, fight it
        if any(not a.changeling_form and a is not self.entity and a is not self.engine.player for a in self.fov_actors):
            return self.goto(self.engine.player.xy)

        else:
            return self.runfrom(self.engine.player.xy)

class InvestigateSightingNPC(DefaultNPC):
    chance_to_chat = 0
    heard_a_sighting = False
    needs_to_investigate = False
    has_to_pee = False
    description = "investigating a sighting"
    short_description = "Θ"

    @property
    def resolve(self):
        if not len(self.engine.sightings):
            return self.parent

    def decide(self):
        for s in self.engine.sightings:
            if s[0] == self.entity.room and s[1] != self.entity.name:
                announcement = random.choice([
                    f"[i]Not seeing a changeling in {s[0].name}. False alarm, I think.",
                    f"[i]Uhh, False alarm. I think {s[1]} has just been at the facility too long.",
                    f"[i]Sorry, {s[1]}, not seeing a changeling in the {s[0].name}."
                ])
                self._intent.append(TalkAction(self.entity,self.entity.x,self.entity.y,announcement))
                self.engine.sightings.remove(s)
                return

        self.goto(random.choice(self.engine.sightings[-1][0].tiles))


class EvacuationNPC(DefaultNPC):
    needs_to_evacuate = False
    heard_a_sighting = False
    needs_to_investigate = False
    has_to_pee = False
    description = "evacuating"
    short_description = "→"

    @property
    def resolve(self):
        return

    def decide(self):
        if not self.engine.gate_unlocked:
            vl = random.choice([
                "*worried muttering*",
                "Get out in the open until the shuttle is unlocked!",
                "Oh god, it's happening!"
            ])
            if random.random() < 0.05:
                self._intent.append(TalkAction(self.entity,0,0,vl))

            if self.entity.is_keyholder:
                self.goto_gate()
            elif self.entity.id % 2 == 0:
                tile = random.choice(self.engine.game_map.shuttle.inner)
                while tile in self.engine.game_map.shuttle.evac_area:
                    tile = random.choice(self.engine.game_map.shuttle.inner)
                self.goto(tile)
            else:
                self.goto(random.choice([r for r in self.engine.game_map.rooms if r.name == "Main Hall"][0].inner))
        else:
            vl = random.choice([
                "Home free!",
                "At last we can get out of here!",
                "I hope that thing isn't with us..."
            ])
            if random.random() < 0.05:
                self._intent.append(TalkAction(self.entity,0,0,vl))

            self.goto(random.choice(self.engine.game_map.shuttle.evac_area))

    def goto_gate(self):
        # if I'm next to the gate, unlock it, else
        if self.entity.distance(*self.engine.game_map.shuttle.gate) < 2:
            self._intent.append(TalkAction(self.entity,0,0,f"[i]I'm unlocking the Shuttle gate. We're home free!"))
            self.engine.gate_unlocked = True
            return
        
        start_intent = len(self._intent)
        di = DIRECTIONS[:]
        random.shuffle(di)
        for d in di:
            self.goto((self.engine.game_map.shuttle.gate[0]+d[0],self.engine.game_map.shuttle.gate[1]+d[1]))
            if len(self._intent) > start_intent:
                break
