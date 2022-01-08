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

	def __init__(self, modifier: int, target):
		self.parent = target
		self._duration_mod = modifier
		self.duration = self.base_duration+self.duration_mod
		self.apply()

	@property
	def duration_mod(self):
		return self._duration_mod

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

