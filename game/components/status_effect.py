from __future__ import annotations

from game.components.base_component import BaseComponent
from game import color

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
	from game.entity import Actor

class StatusEffect(BaseComponent):
	parent: Actor
	label = "<status>"
	description = "(no description)"
	color = color.grey
	base_duration = 10
	base_strengthen_duration = 10

	def __init__(self, target):
		self.parent = target
		self.duration = self.base_duration
		self.apply()

	def decrement(self):
		self.duration -= 1
		if self.duration < 1:
			self.remove()

	def apply(self):
		self.parent.statuses.append(self)

	def remove(self):
		self.parent.statuses.remove(self)
		if self.label and self.parent is self.engine.player:
			self.engine.message_log.add_message(f"You are no longer {self.description}.", color.yellow)
		elif self.label:
			self.engine.message_log.add_message(f"{self.parent.name} is no longer {self.description}.", color.yellow)

	def strengthen(self, modifier:int):
		self._duration_mod = modifier
		self.duration += (self.base_strengthen_duration + self.duration_mod)


class BadStatusEffect(StatusEffect):
	@property
	def duration_mod(self):
		return 0 - self._duration_mod


class EnemyStatusEffect(StatusEffect):
	pass


class ContingentStatusEffect(StatusEffect):
	def __init__(self,target,other):
		self.contingent=other
		super().__init__(target)

class Eating(ContingentStatusEffect):
	base_duration=3
	color=color.changeling

	@property
	def description(self):
		return f"subsuming {self.contingent.name}"

	def cancel(self):
		super().remove()
		eat_status = [i for i in self.contingent.statuses if isinstance(i,BeingEaten)][0]
		eat_status.remove()

	def remove(self):
		self.parent.statuses.remove(self)
		self.engine.message_log.add_message(f"You have finished subsuming {self.contingent.name}.", color.dark_red)
		self.contingent.die()

		self.parent.morph_into(self.contingent)
		self.parent.vigor += 48

	def apply(self):
		super().apply()
		BeingEaten(self.contingent,self.parent)


class BeingEaten(ContingentStatusEffect):
	base_duration=5
	color=color.changeling

	@property
	def description(self):
		return f"being subsumed by {self.contingent.name}"

	def remove(self):
		self.parent.statuses.remove(self)

class Tazed(StatusEffect):
	base_duration = 2
	color=color.cyan
	description="stunned"

	def remove(self):
		self.parent.statuses.remove(self)
