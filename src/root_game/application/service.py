"""Application-layer GameService.

The service coordinates a single game between the rules engine and the
player controllers. It exposes a small turn API:
- `snapshot()` returns the current player's legal actions
- `step()` asks the active controller to choose, then applies the action

This decoupling lets the CLI run with hot-seat humans today and lets a
GUI or AI hook in tomorrow without touching the rules engine.
"""

from dataclasses import dataclass
from typing import Iterable

from root_game.domain.actions import Action
from root_game.domain.enums import Faction, Phase
from root_game.domain.rules import RulesEngine
from root_game.domain.state import GameState

from .controllers import Controller


@dataclass
class TurnSnapshot:
    faction: Faction
    phase: Phase
    turn_count: int
    setup_complete: bool
    setup_step: int
    legal_actions: list[Action]


class GameService:
    def __init__(
        self,
        controllers: dict[Faction, Controller],
        factions: Iterable[Faction] | None = None,
        seed: int | None = None,
    ) -> None:
        self.rules = RulesEngine(seed=seed)
        self.state = GameState.new_game(factions=factions, seed=seed)
        self.controllers = controllers
        for faction in self.state.turn_order:
            if faction not in controllers:
                raise ValueError(f"Controller missing for {faction.name}")

    def snapshot(self) -> TurnSnapshot:
        faction = self.state.current_faction
        legal = self.rules.legal_actions(self.state, faction)
        return TurnSnapshot(
            faction=faction,
            phase=self.state.current_phase,
            turn_count=self.state.turn_count,
            setup_complete=self.state.setup_complete,
            setup_step=self.state.setup_step,
            legal_actions=legal,
        )

    def step(self) -> Action | None:
        snap = self.snapshot()
        if not snap.legal_actions:
            raise RuntimeError("No legal actions available; engine is stuck.")
        controller = self.controllers[snap.faction]
        prompt_label = self._prompt_label(snap)
        idx = controller.choose(snap.faction, snap.legal_actions, prompt_label)
        if idx < 0 or idx >= len(snap.legal_actions):
            raise ValueError("Controller returned out-of-range action index.")
        action = snap.legal_actions[idx]
        self.rules.execute(self.state, action)
        return action

    def is_finished(self) -> bool:
        return self.state.winner is not None

    @staticmethod
    def _prompt_label(snap: TurnSnapshot) -> str:
        if not snap.setup_complete:
            return f"Setup step {snap.setup_step} | {snap.faction.name}"
        return f"Turn {snap.turn_count} | {snap.faction.name} | {snap.phase.name}"
