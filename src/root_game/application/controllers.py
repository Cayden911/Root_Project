"""Player controller abstraction.

Controllers decide which legal action to take when their seat is active.
This lets the same `GameService` drive hot-seat humans now and AI/random
bots later. The CLI today registers a `HumanCliController` for every
seat; future GUIs can register `GuiController` and bots can register
`RandomBotController`, etc.

The contract is intentionally small:
- `choose(snapshot, prompts)` returns the index of the chosen action
  (or raises `KeyboardInterrupt` to abort).
"""

from abc import ABC, abstractmethod
import random
from typing import Callable, Sequence

from root_game.domain.actions import Action
from root_game.domain.enums import Faction


class Controller(ABC):
    @abstractmethod
    def choose(
        self,
        faction: Faction,
        legal_actions: Sequence[Action],
        prompt_label: str,
    ) -> int:
        """Return the index of the chosen action."""


class CallableController(Controller):
    """Adapter that wraps a function; useful for CLI/GUI integration."""

    def __init__(self, fn: Callable[[Faction, Sequence[Action], str], int]) -> None:
        self._fn = fn

    def choose(
        self,
        faction: Faction,
        legal_actions: Sequence[Action],
        prompt_label: str,
    ) -> int:
        return self._fn(faction, legal_actions, prompt_label)


class RandomBotController(Controller):
    """Picks a random legal action (useful for filling seats during dev)."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def choose(
        self,
        faction: Faction,
        legal_actions: Sequence[Action],
        prompt_label: str,
    ) -> int:
        if not legal_actions:
            raise RuntimeError("Random bot has no legal actions to choose from.")
        return self._rng.randrange(len(legal_actions))


class FirstActionController(Controller):
    """Always picks the first legal action (deterministic stub)."""

    def choose(
        self,
        faction: Faction,
        legal_actions: Sequence[Action],
        prompt_label: str,
    ) -> int:
        return 0
