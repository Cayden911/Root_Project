from root_game.application.controllers import FirstActionController
from root_game.application.service import GameService
from root_game.domain.actions import (
    A_MARQUISE_BUILD,
    A_MARQUISE_END_MARCH,
    A_MARQUISE_MARCH,
    A_MOVE,
    Action,
)
from root_game.domain.enums import Faction, Phase
from root_game.domain.faction_state import MarquiseState


def _service_in_marquise_daylight() -> GameService:
    factions = [Faction.MARQUISE, Faction.EYRIE, Faction.ALLIANCE, Faction.VAGABOND]
    service = GameService(
        controllers={f: FirstActionController() for f in factions},
        factions=factions,
        seed=21,
    )
    safety = 50
    while not service.state.setup_complete and safety > 0:
        service.step()
        safety -= 1
    while service.state.current_phase != Phase.DAYLIGHT:
        service.step()
    return service


def test_march_grants_two_moves_for_one_action() -> None:
    service = _service_in_marquise_daylight()
    state = service.state
    ms = state.players[Faction.MARQUISE]
    assert isinstance(ms, MarquiseState)
    initial_actions = ms.actions_remaining
    assert initial_actions == 3

    service.rules.execute(state, Action(Faction.MARQUISE, A_MARQUISE_MARCH))
    assert ms.actions_remaining == initial_actions - 1
    assert ms.march_moves_remaining == 2

    legal = service.rules.legal_actions(state, Faction.MARQUISE)
    assert any(a.action_type == A_MARQUISE_END_MARCH for a in legal)
    move_actions = [a for a in legal if a.action_type == A_MOVE]
    assert move_actions, "Move actions should be available during a March"

    first_move = move_actions[0]
    service.rules.execute(state, first_move)
    assert ms.march_moves_remaining == 1
    assert ms.actions_remaining == initial_actions - 1


def test_build_offered_in_every_ruled_clearing_with_open_slots() -> None:
    service = _service_in_marquise_daylight()
    state = service.state
    legal = service.rules.legal_actions(state, Faction.MARQUISE)
    build_clearings = {
        a.payload["clearing"] for a in legal if a.action_type == A_MARQUISE_BUILD
    }
    expected = {
        cid
        for cid, clearing in state.board.clearings.items()
        if clearing.ruling_faction(eyrie_lords_of_forest=True) == Faction.MARQUISE
        and clearing.open_slots() > 0
    }
    assert expected, "Marquise should rule at least a few clearings on turn 1"
    assert len(expected) > 1, (
        "Marquise should rule more than one clearing on turn 1"
    )
    assert build_clearings == expected, (
        f"Build offered in {sorted(build_clearings)}, expected {sorted(expected)}"
    )


def test_end_march_does_not_consume_remaining_action() -> None:
    service = _service_in_marquise_daylight()
    state = service.state
    ms = state.players[Faction.MARQUISE]
    assert isinstance(ms, MarquiseState)
    initial_actions = ms.actions_remaining

    service.rules.execute(state, Action(Faction.MARQUISE, A_MARQUISE_MARCH))
    service.rules.execute(state, Action(Faction.MARQUISE, A_MARQUISE_END_MARCH))
    assert ms.march_moves_remaining == 0
    assert ms.actions_remaining == initial_actions - 1
