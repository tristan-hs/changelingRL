from __future__ import annotations

from typing import List, TYPE_CHECKING

from game.components.base_component import BaseComponent
from game import color
from game.render_order import RenderOrder

if TYPE_CHECKING:
    from game.entity import Actor, Item


class Inventory(BaseComponent):
    parent: Actor

    def __init__(self):
        self.items: List[Item] = []