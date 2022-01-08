from __future__ import annotations

from typing import Tuple, TYPE_CHECKING

import random

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

def render_dungeon_level(
    console: Console, dungeon_level: int, location: Tuple[int, int], turn_count: int, do_turn_count: bool
) -> None:
    """
    Render the level the player is currently on, at the given location.
    """
    x, y = location
    x -= 1
    c = color.grey
    dungeon_level = dungeon_level if len(str(dungeon_level)) > 1 else f"0{dungeon_level}"

    if do_turn_count:
        turn_count = str(turn_count)
        for i in [9,99,999]:
            if int(turn_count) < i:
                turn_count = '0' + turn_count
        if int(turn_count) > 99999:
            turn_count = ' bruh'
        if int(turn_count) > 9999:
            turn_count = turn_count[0]+turn_count[1]+'.'+turn_count[2]+'k'

        console.draw_frame(
            x=x-2,
            y=+2,
            width=8,
            height=3,
            clear=True,
            fg=color.grey,
            bg=(0,0,0)
        )
        console.print(x=x-1,y=y+3,string=f"T{turn_count}", fg=color.grey)

    console.draw_frame(
        x=x,
        y=y,
        width=5,
        height=3,
        clear=True,
        fg=c,
        bg=(0,0,0)
    )
    console.print(x=x+1, y=y+1, string=f"D{dungeon_level}", fg=c)

def render_instructions(console: Console, location: Tuple[int,int]) -> None:
    x, y = location
    l0 = f"{D_KEYS[2]} {D_KEYS[0]} {D_KEYS[5]} (?)info"
    l1 = f" {D_ARROWS[2]}{D_ARROWS[0]}{D_ARROWS[5]}  (.)wait"
    l2 = f"{D_KEYS[3]}{D_ARROWS[3]}.{D_ARROWS[6]}{D_KEYS[6]} (>)descend"
    l3 = f" {D_ARROWS[4]}{D_ARROWS[1]}{D_ARROWS[7]}  (i)nventory"
    l4 = f"{D_KEYS[4]} {D_KEYS[1]} {D_KEYS[7]}"
    l5 = "      "
    l7 = "     e(x)amine"
    l6 = "    re(v)iew"
    l8 = f"   per(c)eive"

    for i,l in enumerate([l0,l1,l2,l3,l4,l5,l6,l7,l8]):
        console.print(x=x, y=y+i, string=l, fg=color.dark_grey)

def render_names_at_mouse_location(
    console: Console, x: int, y: int, engine: Engine
) -> None:
    mouse_x, mouse_y = engine.mouse_location

    if not engine.game_map.in_bounds(mouse_x, mouse_y):
        return

    entities = engine.mouse_things

    chars = ALPHA_CHARS[:]
    for e,entity in enumerate(entities):
        if e == len(entities)-1 and (engine.game_map.visible[mouse_x,mouse_y] or engine.game_map.explored[mouse_x,mouse_y] or engine.game_map.mapped[mouse_x,mouse_y]):
            tile = engine.game_map.tiles['light'][mouse_x,mouse_y]
            name = NAMES[entity[5]]
            fg = color.grey
            console.print(x+3,y+e,chr(tile[0]),tuple(tile[1]),tuple(tile[2]))
        else:
            engine.game_map.print_tile(entity,(x+3,y+e),console)
            name = entity.label if len(entity.label) > 1 else '???'
            fg = entity.color
        
        name = name if len(name) < 13 else name[:10]+'..'
        console.print(x,y+e,chars.pop(0)+')',fg=fg)
        console.print(x+5,y+e,name,fg=fg)
        if e > 6:
            console.print(x+1,y+e+1,'...',fg=color.offwhite)
            break



def print_fov_actors(console,player,xy):
    x,y = xy
    chars = ALPHA_CHARS[:]
    for actor in sorted(list(player.gamemap.actors),key=lambda a:a.id):
        if actor is player:
            continue
        if player.gamemap.print_actor_tile(actor,(x+3,y),console):
            known = (player.gamemap.visible[actor.x,actor.y] or player.gamemap.smellable(actor,True))
            name = actor.name if known else '???'
            if len(name) > 12:
                name = name[:10]+'..'
            fg = actor.color if known else color.yellow
            if known:
                console.print(x,y,f"{chars.pop(0)})",fg=fg)
            console.print(x+5,y,name,fg=fg)
            y += 1
            if y > 48:
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

    console.print(6,49,"(c)ontrols",color.dark_grey)

