"""Renderer interface — one implementation per output format."""
from abc import ABC, abstractmethod


class Renderer(ABC):
    @abstractmethod
    def quest_tree(self, main_quests: list, side_quests: list, state: dict) -> None:
        """Render the grouped quest listing."""

    @abstractmethod
    def status(self, state: dict, focused: list) -> None:
        """Render the character sheet."""

    @abstractmethod
    def summary(self, data: dict) -> None:
        """Render the daily summary from prepared data."""
