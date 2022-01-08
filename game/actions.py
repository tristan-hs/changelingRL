from __future__ import annotations

from typing import Optional, Tuple, TYPE_CHECKING

from game.render_functions import DIRECTIONS
from game import color, exceptions

if TYPE_CHECKING:
    from game.engine import Engine
    from game.entity import Actor, Entity


class Action:
    meleed = False
    
    def __init__(self, entity: Actor) -> None:
        super().__init__()
        self.entity = entity

    @property
    def engine(self) -> Engine:
        """Return the engine this action belongs to."""
        return self.entity.gamemap.engine

    def perform(self) -> None:
        """Perform this action with the objects needed to determine its scope.

        `self.engine` is the scope this action is being performed in.

        `self.entity` is the object performing the action.

        This method must be overridden by Action subclasses.
        """
        raise NotImplementedError()


class PickupAction(Action):
    """Pickup an item and add it to the inventory, if there is room for it."""

    def __init__(self, entity: Actor, items=None):
        super().__init__(entity)
        self.items = items

    @property
    def items_here(self):
        return [i for i in self.engine.game_map.items if i.xy == self.entity.xy and i not in self.entity.inventory.items]

    def perform(self) -> None:
        items = self.items if self.items else self.items_here

        for item in items:
            item.parent = self.entity.inventory
            item.parent.items.append(item)
            self.engine.message_log.add_message(f"You pick up the ?.", color.offwhite, item.label, item.color)
            self.engine.history.append(("pickup item",item.name,self.engine.turn_count))


class ItemAction(Action):
    def __init__(
        self, entity: Actor, item: Item, target_xy: Optional[Tuple[int, int]] = None, target_item: Optional[Item] = None
    ):
        super().__init__(entity)
        self.item = item
        if not target_xy:
            target_xy = entity.x, entity.y
        self.target_xy = target_xy
        self._target_item = target_item

    @property
    def target_item(self) -> Optional[Item]:
        return self._target_item

    @property
    def target_actor(self) -> Optional[Actor]:
        """Return the actor at this actions destination."""
        return self.engine.game_map.get_actor_at_location(*self.target_xy)

    def perform(self) -> None:
        """Invoke the items ability, this action will be given to provide context."""
        self.engine.message_log.add_message(f"You use the ?.", color.offwhite, self.item.label, self.item.color)
        self.do_perform()

    def do_perform(self) -> None:
        self.item.usable.start_activation(self)
        self.engine.history.append(("use item",self.item.name,self.engine.turn_count))


class ThrowItem(ItemAction):
    def perform(self, at="actor") -> None:
        target = self.target_actor if at == "actor" else self.target_item
        at = f" on the {target.name}" if target and target is not self.engine.player else ''        
        self.engine.message_log.add_message(f"You use the ?{at}.", color.offwhite, self.item.label, self.item.color)
        self.do_perform()

    @property
    def target_item(self) -> Optional[Item]:
        return self.engine.game_map.get_item_at_location(*self.target_xy)


class ActionWithDirection(Action):
    def __init__(self, entity: Actor, dx: int, dy: int):
        super().__init__(entity)

        self.dx = dx
        self.dy = dy
    
    @property
    def dest_xy(self) -> Tuple[int, int]:
        """Returns this actions destination."""
        return self.entity.x + self.dx, self.entity.y + self.dy

    @property
    def blocking_entity(self) -> Optional[Entity]:
        """Return the blocking entity at this actions destination.."""
        return self.engine.game_map.get_blocking_entity_at_location(*self.dest_xy)

    @property
    def target_item(self) -> Optional[Item]:
        """Return the actor at this actions destination."""
        return self.engine.game_map.get_item_at_location(self.entity.x,self.entity.y)

    @property
    def target_actor(self) -> Optional[Actor]:
        """Return the actor at this actions destination."""
        return self.engine.game_map.get_actor_at_location(*self.dest_xy)


class MeleeAction(ActionWithDirection):
    def perform(self) -> None:
        target = self.blocking_entity
        if not target:
            raise exceptions.Impossible("Nothing to attack.")

        damage = 1
        label = target.name
        attack_desc = f"{self.entity.name.capitalize()} attacks {label}!"
            
        if damage > 0:
            self.engine.message_log.add_message(
                attack_desc, color.offwhite
            )
            target.take_damage(damage)
            if target is self.engine.player and not target.is_alive:
                target.cause_of_death = self.entity.name
        else:
            self.engine.message_log.add_message(
                f"{attack_desc} But it does no damage.", color.offwhite
            )

class TalkAction(ActionWithDirection):
    def perform(self) -> None:
        target = self.blocking_entity
        self.engine.message_log.add_message(
            f"?: Hello there, {target.name}!", color.offwhite, self.entity.label, self.entity.color
        )


class BumpAction(ActionWithDirection):
    def perform(self) -> None:
        if self.blocking_entity:
            self.meleed = True
            return TalkAction(self.entity, self.dx, self.dy).perform()

        return MovementAction(self.entity, self.dx, self.dy).perform()


class MovementAction(ActionWithDirection):
    def perform(self) -> None:
        if self.entity is self.engine.player:
            if not self.engine.game_map.tile_is_walkable(*self.dest_xy):
                raise exceptions.Impossible("That way is blocked.")

            self.entity.move(self.dx,self.dy)

        else:
            if not self.engine.game_map.tile_is_walkable(*self.dest_xy):
                raise exceptions.Impossible("That way is blocked.")

            self.entity.move(self.dx,self.dy)


class WaitAction(Action):
    def perform(self) -> None:
        pass

class TakeStairsAction(Action):
    def perform(self) -> None:
        """
        Take the stairs, if any exist at the entity's location.
        """
        
        if (self.entity.x, self.entity.y) == self.engine.game_map.downstairs_location:
            self.engine.game_world.generate_floor()
            self.engine.message_log.add_message(
                "You descend the staircase.", color.purple
            )
            self.engine.history.append(("descend stairs",self.engine.game_map.floor_number,self.engine.turn_count))
        else:
            raise exceptions.Impossible("There are no stairs here.")
