from __future__ import annotations

from typing import Tuple, TYPE_CHECKING

import random
import math

from game import color
from game.message_log import MessageLog
from game.render_order import RenderOrder
from game.tile_types import NAMES, FLAVORS

if TYPE_CHECKING:
    from tcod import Console
    from game.engine import Engine
    from game.game_map import GameMap

DIRECTIONS = [(0,-1),(0,1),(-1,-1),(-1,0),(-1,1),(1,-1),(1,0),(1,1)]
D_ARROWS = ['↑', '↓', '\\', '←', '/', '/','→','\\']
D_KEYS = ['K','J','Y','H','B','U','L','N']
ALPHA_CHARS = ['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R','S','T','U','V','W','X','Y','Z']

def render_run_info(
    console: Console, turn_count: int, player
) -> None:

    random.seed(turn_count*player.x*player.y)

    def morph(s,f=0.1):

        if s == '\n':
            return s
        if random.random()<f:
            return s.upper()
        if random.random()<f:
            return s.lower()
        if random.random()<f/2:
            return '@'
        if random.random()<f:
            return random.choice(['~','`','☺','☻','♂','♀','►','↕','¶','§','æ','¿','¼','⌐','¬','Θ','φ','²'])
        if random.random()<f/2:
            return random.choice(['▬','«','░','▒','▓','╖','╣','╛','╬','█','▄','▌','▐','▀','■'])
        return s



    """
    Render the level the player is currently on, at the given location.
    """
    c = color.grey

    # render day x + clock time

    day = math.floor(turn_count / 480)+1
    day = f"{day}" if day > 9 else f"0{day}"

    hour = math.floor(turn_count/20) % 24
    hour = f"{hour}" if hour > 9 else f"0{hour}"

    minute = (turn_count*3) % 60
    minute = f"{minute}" if minute > 9 else f"0{minute}"

    console.print(71,1,f"{hour}:{minute}")
    console.print(61,1,f"Day {day}")

    
    if not player.changeling_form:
        console.draw_frame(70,3,9,5,fg=color.offwhite)
        for i,b in enumerate(player.bumps):
            c = color.offwhite if i == player.bump_index else color.grey
            a = ' ←' if i == player.bump_index else ''
            s = ' ' if b == 'EAT' else ''
            console.print(72,4+i,f"{b}{s}{a}",fg=c)

        for i in range(3):
            console.print(70,4+i,"TAB"[i],fg=color.black,bg=color.offwhite)
    else:
        console.draw_frame(70,3,9,5,fg=color.dark_red)
        for i in range(6):
            console.print(72,4+i,''.join([morph(a) for a in "EAT ←"]),fg=color.dark_red)
        for i in range(3):
            console.print(70,4+i,morph("EAT"[i]),fg=color.black,bg=color.dark_red)

    if not player.changeling_form:
        console.draw_frame(60,3,9,4)
        console.print_box(61,3,2,1,"ID")
        console.print_box(61,4,7,2,player.name,fg=player.color)
    else:
        console.draw_frame(60,3,12,4,fg=color.changeling)
        name = "changeling\n░░░░░░░░░░"
        name = ''.join([morph(a) for a in name])
        console.print(61,4,name,fg=color.changeling)

    if not player.changeling_form:
        console.draw_frame(60,8,20,6)
        console.print_box(61,8,8,1,"SCHEDULE")
        times = list(player.schedule.keys())
        times.sort()
        sched = ''
        for j,i in enumerate(times):
            k = f"0{i}" if i < 10 else i
            n = player.schedule[i].name
            if len(n) > 10:
                n = n[:8]+'..'
            sched = f"{k}:00 - {n}"
            c = color.offwhite if player.schedule[i] is player.scheduled_room else color.grey
            console.print(61,9+j,sched,c)

    else:
        c = color.changeling
        if random.random()<0.05:
            c = color.dark_red
        console.draw_frame(60,8,20,6,fg=c)
        n = "SCHEDULE"
        console.print_box(61,8,8,1,n,fg=c)
        for i in range(4):
            n = 'eateateateateateat'
            if random.random()<0.05:
                n += 'e'
            x = 59 if random.random()<0.05 else 61
            n = ''.join([morph(a) for a in n])
            console.print(x,9+i,n,color.dark_red)

    if not player.changeling_form:
        console.draw_frame(60,15,20,10)
        console.print_box(61,15,12,1,"SURROUNDINGS")
    else:
        c = color.dark_red if random.random() < 0.05 else color.changeling
        console.draw_frame(60,15,20,10,fg=c)
        n = "SURROUNDINGS"
        console.print_box(61,15,12,1,n)

    if not player.changeling_form:
        c = color.dark_red if player.just_took_damage else color.offwhite
        console.draw_frame(60,26,20,24,fg=c)
        console.print_box(61,26,3,1, "LOG")
    else:
        c = color.dark_red if player.just_took_damage else color.changeling
        console.draw_frame(60,26,20,24,fg=c)
        console.print_box(61,26,3,1,"LOG")

    c = color.changeling if player.changeling_form else color.offwhite
    console.draw_frame(57,0,3,50,fg=c)

    y = 49-player.vigor
    v = player.vigor

    c = color.dark_red if v < 25 else color.changeling
    if not player.changeling_form and v == 48:
        c = color.offwhite

    console.print_box(58,y,1,v,"█\n"*v,fg=c)

    for k,i in enumerate("VIGOR"):
        c1 = c if v < 5-k else color.black
        c2 = color.black if v < 5-k else c
        console.print(58,44+k,i,fg=c1,bg=c2)

def render_instructions(console: Console, location: Tuple[int,int]) -> None:
    pass

def render_names_at_mouse_location(
    console: Console, x: int, y: int, engine: Engine
) -> None:
    mouse_x, mouse_y = engine.mouse_location
    x,y = (61,17)

    if not engine.game_map.in_bounds(mouse_x, mouse_y):
        return

    room = engine.game_map.room_at_location(mouse_x,mouse_y)
    if engine.game_map.explored[mouse_x,mouse_y]:
        console.print(61,16,room,fg=color.grey)
    else:
        y -= 1

    entities = engine.mouse_things

    chars = ALPHA_CHARS[:]
    for e,entity in enumerate(entities):
        if e == len(entities)-1 and (engine.game_map.visible[mouse_x,mouse_y] or engine.game_map.explored[mouse_x,mouse_y] or engine.game_map.mapped[mouse_x,mouse_y]):
            tile = engine.game_map.tiles['light'][mouse_x,mouse_y]
            name = NAMES[entity[5]]
            fg = color.grey
            console.print(x+3,y+e,chr(tile[0]),tuple(tile[1]),tuple(tile[2]))
            x_mod = 2
        else:
            # engine.game_map.print_tile(entity,(x+3,y+e),console)
            name = entity.label if len(entity.label) > 1 else '???'
            sd = entity.ai.short_description
            fg = entity.color
            console.print(79-len(sd),y,sd,fg=fg)
            x_mod = 0
        
        name = name if len(name) < 13 else name[:10]+'..'
        console.print(x,y+e,chars.pop(0)+')',fg=fg)
        console.print(x+3+x_mod,y+e,name,fg=fg)
        if e > 6:
            console.print(x+1,y+e+1,'...',fg=color.offwhite)
            break



def print_fov_actors(console,player,xy):
    x,y = (61,17)

    room = player.engine.game_map.room_at_location(player.x,player.y)
    # room += f" {player.x},{player.y}"
    console.print(61,16,room,fg=color.grey)

    chars = ALPHA_CHARS[:]
    for actor in sorted(list(player.gamemap.actors),key=lambda a:a.id):
        if actor is player:
            continue
        if player.gamemap.visible[actor.x,actor.y] or player.gamemap.smellable(actor):
            known = (player.gamemap.visible[actor.x,actor.y] or player.gamemap.smellable(actor,True))
            name = actor.name if known else '???'
            if len(name) > 11:
                name = name[:9]+'..'
            fg = actor.color if known else color.yellow
            if known:
                console.print(x,y,f"{chars.pop(0)})",fg=fg)
            console.print(x+3,y,name,fg=fg)

            sd = actor.ai.short_description
            console.print(79-len(sd),y,sd,fg=fg)
            y += 1
            if y > 22:
                console.print(x+1,y,'...',fg=color.offwhite)
                break

    xs,ys = player.gamemap.downstairs_location
    if player.gamemap.visible[xs,ys]:
        tile = player.gamemap.tiles['light'][xs,ys]
        name = NAMES[player.gamemap.tiles[xs,ys][5]]
        fg = color.grey
        console.print(x+3,y,chr(tile[0]),tuple(tile[1]),tuple(tile[2]))

        if len(name) > 12:
            name = name[:10]+'..'
        console.print(x,y,f"{chars.pop(0)})",fg=fg)
        console.print(x+5,y,name,fg=fg)

