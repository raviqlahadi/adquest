"""adquest — Gamified task management RPG CLI."""
__version__ = "1.2.0"

from .errors import QuestError
from .cli import main

__all__ = ["main", "QuestError", "__version__"]
