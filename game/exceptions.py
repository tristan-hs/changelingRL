class Impossible(Exception):
    """Exception raised when an action is impossible to be performed.

    The reason is given as the exception message.
    """

class QuitWithoutSaving(SystemExit):
    """Can be raised to exit the game without automatically saving."""


class UnorderedPickup(Exception):
	""" Raise to order pickups before picking them up """


class ToggleFullscreen(Exception):
	"""Raise to toggle fullscreen"""

class QuitToMenu(Exception):
	"""Quit from game to main menu"""

class PickBumpType(Exception):
	"""Player needs to pick what happens when they bump"""

class NewGame(Exception):
	def __init__(self,meta):
		super().__init__()
		self.meta = meta