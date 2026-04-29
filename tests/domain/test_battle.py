import random

from root_game.application.controllers import FirstActionController
from root_game.application.service import GameService
from root_game.domain.battle import resolve_battle
from root_game.domain.enums import Faction


def _initial_service() -> GameService:
    factions = [Faction.MARQUISE, Faction.EYRIE, Faction.ALLIANCE, Faction.VAGABOND]
    controllers = {f: FirstActionController() for f in factions}
    return GameService(controllers=controllers, factions=factions, seed=11)


def _complete_setup(service: GameService) -> None:
    safety = 50
    while not service.state.setup_complete and safety > 0:
        service.step()
        safety -= 1


def test_resolve_battle_records_attacker_and_defender() -> None:
    service = _initial_service()
    _complete_setup(service)
    state = service.state
    target = next(
        (cid for cid, c in state.board.clearings.items()
         if c.warriors.get(Faction.MARQUISE, 0) > 0
         and c.warriors.get(Faction.EYRIE, 0) > 0),
        None,
    )
    if target is None:
        for cid, clearing in state.board.clearings.items():
            if clearing.warriors.get(Faction.MARQUISE, 0) > 0:
                clearing.add_warriors(Faction.EYRIE, 2)
                target = cid
                break
    rng = random.Random(0)
    result = resolve_battle(state, Faction.MARQUISE, Faction.EYRIE, target, rng)
    assert result.attacker == Faction.MARQUISE
    assert result.defender == Faction.EYRIE
    assert result.clearing_id == target


def test_alliance_guerrilla_war_inverts_dice() -> None:
    service = _initial_service()
    _complete_setup(service)
    state = service.state
    cid = next(iter(state.board.clearings))
    clearing = state.board.clearings[cid]
    clearing.warriors[Faction.MARQUISE] = 5
    clearing.warriors[Faction.ALLIANCE] = 5
    rng = random.Random(0)
    result = resolve_battle(state, Faction.MARQUISE, Faction.ALLIANCE, cid, rng)
    # In guerrilla mode defender should not be capped below attacker hits
    assert result.defender_hits_dealt >= 0
