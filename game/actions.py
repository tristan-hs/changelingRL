from __future__ import annotations

from typing import Optional, Tuple, TYPE_CHECKING

from game.render_functions import DIRECTIONS
from game import color, exceptions
from game.components.status_effect import Tazed

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


class TazeAction(ActionWithDirection):
    def perform(self) -> None:
        target = self.blocking_entity
        if not target:
            raise exceptions.Impossible("Nothing to attack.")

        label = target.name if target is not self.engine.player else 'you'
        attack_desc = f"{self.entity.name.capitalize()} tazes {label}!"

        self.engine.message_log.add_message(attack_desc, color.cyan)

        self.entity.ai.just_tazed = target
        # Tazed(target)
        if target is self.engine.player:
            target.take_damage(12)


class EatAction(ActionWithDirection):
    def perform(self) -> None:
        target = self.blocking_entity
        if not target:
            raise exceptions.Impossible("Nothing to eat.")
        self.entity.eat(target)



class TalkAction(ActionWithDirection):
    def __init__(self,entity,dx,dy,line=None):
        super().__init__(entity,dx,dy)
        self.line = line

    def perform(self) -> None:
        target = self.blocking_entity
        if target == self.entity:
            target = None

        vl = self.entity.get_voice_line(target) if not self.line else self.line
        pf = "?: "
        if vl[:3] == '[i]':
            pf = "[intercom]\n"+pf
            vl = vl[3:]
        if vl and (pf[0] == '[' or self.entity.fov[self.engine.player.x,self.engine.player.y]):
            self.engine.message_log.add_message(
                pf+vl, color.offwhite, self.entity.label, self.entity.color
            )


class BumpAction(ActionWithDirection):
    def perform(self) -> None:
        if self.blocking_entity:
            self.meleed = True

            if self.entity is self.engine.player and not self.entity.changeling_form:
                if self.entity.bumps[self.entity.bump_index] == 'EAT':
                    return EatAction(self.entity,self.dx,self.dy).perform()
                else:
                    return TalkAction(self.entity,self.dx,self.dy).perform()
            elif self.entity is self.engine.player:
                return EatAction(self.entity, self.dx, self.dy).perform()

            return TalkAction(self.entity, self.dx, self.dy).perform()

        return MovementAction(self.entity, self.dx, self.dy).perform()


class MovementAction(ActionWithDirection):
    def perform(self) -> None:
        if self.entity is self.engine.player:
            self.entity.cancel_eat()

        if not self.engine.game_map.tile_is_walkable(*self.dest_xy):
            raise exceptions.Impossible("That way is blocked.")

        self.entity.move(self.dx,self.dy)

        if self.entity is self.engine.player and self.entity.xy == self.engine.game_map.shuttle.gate and not self.engine.bioscanner_dismantled:
            self.engine.message_log.add_message("CHANGELING DETECTED", color.yellow)
            self.engine.message_log.add_message("Electric currents from the bioscanner fry your alien brain.", color.offwhite)
            self.engine.player.take_damage(100)


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
