from typing import Tuple

import numpy as np  # type: ignore

# Tile graphics structured type compatible with Console.tiles_rgb.
graphic_dt = np.dtype(
    [
        ("ch", np.int32),  # Unicode codepoint.
        ("fg", "3B"),  # 3 unsigned bytes, for RGB colors.
        ("bg", "3B"),
    ]
)

# Tile struct used for statically defined tile data.
tile_dt = np.dtype(
    [
        ("walkable", np.bool),  # True if this tile can be walked over.
        ("placeholder",None),
        ("transparent", np.bool),  # True if this tile doesn't block FOV.
        ("dark", graphic_dt),  # Graphics for when this tile is not in FOV.
        ("light", graphic_dt),  # Graphics for when the tile is in FOV.
        ("name",np.int32),
        ("flavor",np.int32)
    ]
)

NAMES = []
FLAVORS = []

def new_tile(
    *,  # Enforce the use of keywords, so that parameter order doesn't matter.
    walkable: int,
    transparent: int,
    dark: Tuple[int, Tuple[int, int, int], Tuple[int, int, int]],
    light: Tuple[int, Tuple[int, int, int], Tuple[int, int, int]],
    name: int,
    flavor: int
) -> np.ndarray:
    """Helper function for defining individual tile types """

    if name in NAMES:
        name = NAMES.index(name)
    else:
        NAMES.append(name)
        name = len(NAMES)-1

    if flavor in FLAVORS:
        flavor = FLAVORS.index(flavor)
    else:
        FLAVORS.append(flavor)
        flavor = len(FLAVORS)-1

    placeholder = None

    return np.array((walkable, placeholder, transparent, dark, light, name, flavor), dtype=tile_dt)


# SHROUD represents unexplored, unseen tiles
SHROUD = np.array((ord(" "), (255, 255, 255), (0, 0, 0)), dtype=graphic_dt)
# MAPPED representes unexplored, mapped tiles
MAPPED = np.array((ord("."), (100,0,100), (0,0,0)), dtype=graphic_dt)

floor = new_tile(
    name='floor',
    flavor='When you fall, it will be there for you.',
    walkable=True,
    transparent=True,
    dark=(ord(" "), (50,50,50), (7,7,7)),
    light=(ord("."), (25,25,25), (10,10,10)),
)

bloody_floor = new_tile(
    name='floor',
    flavor='Stained with the viscera of your victims.',
    walkable=True,
    transparent=True,
    dark=(ord(" "), (50,50,50), (7,7,7)),
    light=(ord("."), (75,0,0), (10,10,10))
)
wall = new_tile(
    name='wall',
    flavor='Solid inanimate material.',
    walkable=False,
    transparent=False,
    dark=(ord(" "), (255, 255, 255), (25,25,30)),
    light=(ord(" "), (255, 255, 255), (50,50,60)),
)
down_stairs = new_tile(
    name='stairs',
    flavor='Your passage to the next level.',
    walkable=True,
    transparent=True,
    dark=(ord(">"), (0, 100, 0), (0,5,0)),
    light=(ord(">"), (0, 255, 0), (0,10,0)),
)
door = new_tile(
    name='doorway',
    flavor='The threshold between rooms.',
    walkable=True,
    transparent=False,
    dark=(ord("+"), (100,50,50), (5,5,5)),
    light=(ord("+"), (150,75,75), (10,10,10))
)


gate = new_tile(
    name='shuttle gate',
    flavor='The only way into the evacuation area. Be sure to dismantle the bioscanner before using.',
    walkable=True,
    transparent=True,
    dark=(ord("░"), (50,50,50), (5,5,5)),
    light=(ord("░"), (75,150,75), (10,10,10))
)
locked_gate = new_tile(
    name='locked gate',
    flavor='The only way into the evacuation area. Subsume a keyholder and dismantle the bioscanner to gain access.',
    walkable=False,
    transparent=True,
    dark=(ord("+"),(50,50,50),(5,5,5)),
    light=(ord("+"),(75,150,75),(10,10,10))
)
fence = new_tile(
    name='fence',
    flavor='A sturdy barrier.',
    walkable=False,
    transparent=True,
    dark=(ord("┼"), (100,50,50), (7,7,7)),
    light=(ord("┼"), (150,75,75), (10,10,10)),
)
evac_area = new_tile(
    name='floor',
    flavor='When you fall, it will be there for you.',
    walkable=True,
    transparent=True,
    dark=(ord(" "), (50,50,50), (7,10,7)),
    light=(ord("."), (25,25,25), (10,20,10)),
)
bioscanner = new_tile(
    name='bioscanner',
    flavor='Scans the genetic content of any who pass through the nearby gate, tazing any existential threats to humanity.',
    walkable=False,
    transparent=True,
    dark=(ord("╬"), (50,50,50), (25,0,25)),
    light=(ord("╬"), (75,150,75), (50,0,50))
)
dismantled_bioscanner = new_tile(
    name='bioscanner',
    flavor='WARNING: Bioscanner critically damaged. Repair ASAP.',
    walkable=False,
    transparent=True,
    dark=(ord("╬"), (50,50,50), (25,0,25)),
    light=(ord("╬"), (200,75,75), (50,0,50))
)