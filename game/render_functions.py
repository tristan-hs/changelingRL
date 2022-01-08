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
    """
    Render the level the player is currently on, at the given location.
    """
    c = color.grey

    # render day x + clock time

    day = math.floor(turn_count / 480)
    day = f"{day}" if day > 9 else f"0{day}"

    hour = math.floor(turn_count/20) % 24
    hour = f"{hour}" if hour > 9 else f"0{hour}"

    minute = (turn_count*3) % 60
    minute = f"{minute}" if minute > 9 else f"0{minute}"

    console.print(66,1,f"{hour}:{minute}, day {day}")

    console.draw_frame(60,3,20,4)
    console.print_box(61,3,2,1,"ID")
    console.print_box(61,4,18,2,"John Doe\nFurnace Operator",fg=player.color)

    console.draw_frame(60,8,20,6)
    console.print_box(61,8,8,1,"SCHEDULE")
    console.print_box(61,9,18,4,"07:00 - Dining H.\n12:00 - Workshop\n18:00 - Deli\n22:00 - Bunks",fg=color.grey)

    console.draw_frame(60,15,20,10)
    console.print_box(61,15,12,1,"SURROUNDINGS")

    console.draw_frame(60,26,20,24)
    console.print_box(61,26,3,1, "LOG")

def render_instructions(console: Console, location: Tuple[int,int]) -> None:
    pass

def render_names_at_mouse_location(
    console: Console, x: int, y: int, engine: Engine
) -> None:
    mouse_x, mouse_y = engine.mouse_location
    x,y = (61,17)

    room = engine.game_map.room_at_location(mouse_x,mouse_y)
    room += f" {mouse_x},{mouse_y}"
    console.print(61,16,room,fg=color.grey)

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
    x,y = (61,17)

    room = player.engine.game_map.room_at_location(player.x,player.y)
    room += f" {player.x},{player.y}"
    console.print(61,16,room,fg=color.grey)

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

