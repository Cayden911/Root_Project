from dataclasses import dataclass
from typing import Protocol

from root_game.domain.actions import Action


@dataclass
class ViewState:
    header: str
    board_lines: list[str]
    action_labels: list[str]


class GamePresenter(Protocol):
    def build_view(self) -> ViewState:
        """Return UI-ready view state without mutating game logic."""


class GameController(Protocol):
    def dispatch(self, action: Action) -> None:
        """Forward a selected action into application service."""

