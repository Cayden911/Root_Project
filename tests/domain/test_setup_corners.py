"""Regression: every corner must have enough open slots in keep+adjacent
so the Marquise's 3 starting buildings (Law 6.3.4) always fit."""

from root_game.application.controllers import FirstActionController
from root_game.application.service import GameService
from root_game.domain.actions import (
    A_SETUP_PLACE_KEEP,
    A_SETUP_PLACE_STARTING_BUILDING,
    Action,
)
from root_game.domain.enums import (
    CORNER_CLEARINGS,
    BuildingType,
    Faction,
)
from root_game.domain.faction_state import MarquiseState


def _bootstrap_service() -> GameService:
    factions = [Faction.MARQUISE, Faction.EYRIE, Faction.ALLIANCE, Faction.VAGABOND]
    return GameService(
        controllers={f: FirstActionController() for f in factions},
        factions=factions,
        seed=3,
    )


def test_every_corner_keep_choice_fits_three_starting_buildings() -> None:
    for corner in CORNER_CLEARINGS:
        service = _bootstrap_service()
        state = service.state
        rules = service.rules
        # Place keep at this corner
        rules.execute(state, Action(Faction.MARQUISE, A_SETUP_PLACE_KEEP, {"clearing": corner}))
        ms = state.players[Faction.MARQUISE]
        assert isinstance(ms, MarquiseState)
        # Place each remaining starting building somewhere legal
        for _ in range(3):
            legal = rules.legal_actions(state, Faction.MARQUISE)
            building_actions = [a for a in legal if a.action_type == A_SETUP_PLACE_STARTING_BUILDING]
            assert building_actions, (
                f"No valid building placement for corner {corner}; ms.starting_buildings_remaining"
                f" = {[b.name for b in ms.starting_buildings_remaining]}"
            )
            rules.execute(state, building_actions[0])
        assert not ms.starting_buildings_remaining
        # Confirm 3 Marquise buildings landed on the map
        placed = sum(
            sum(
                1
                for owner, kind in clearing.buildings
                if owner == Faction.MARQUISE and kind in {
                    BuildingType.SAWMILL,
                    BuildingType.WORKSHOP,
                    BuildingType.RECRUITER,
                }
            )
            for clearing in state.board.clearings.values()
        )
        assert placed == 3
