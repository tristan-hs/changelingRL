import random

from game.components import ai, consumable
from game.entity import Actor, Item
from game import color
from game.render_order import RenderOrder
 
player = Actor(
    char="@",
    color=color.player,
    name="You",
    ai_cls=ai.HostileEnemy,
    render_order=RenderOrder.PLAYER,
    description="That's you!"
)

goblin = Actor(
	char="g",
	color=(20,150,20),
	name="Goblin",
	ai_cls=ai.HostileEnemy,
	render_order = RenderOrder.ACTOR,
	description="gobgobgob"
)

enemy_sets = [
[goblin],
[goblin],
[goblin],
[goblin],
[goblin],
[goblin],
[goblin],
[goblin],
[goblin],
[goblin]
]

rock = Item(
	color = color.grey,
	name='rock',
	usable=consumable.DamagingProjectile(damage=1),
	flavor='do not place in mouth'
)

item_factories = [rock]