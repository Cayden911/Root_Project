from root_game.application.controllers import FirstActionController
from root_game.application.service import GameService
from root_game.domain.enums import Faction, Phase


def _service() -> GameService:
    factions = [Faction.MARQUISE, Faction.EYRIE, Faction.ALLIANCE, Faction.VAGABOND]
    controllers = {f: FirstActionController() for f in factions}
    return GameService(controllers=controllers, factions=factions, seed=99)


def test_service_runs_until_setup_complete() -> None:
    service = _service()
    safety = 60
    while not service.state.setup_complete and safety > 0:
        service.step()
        safety -= 1
    assert service.state.setup_complete
    assert service.state.turn_count >= 1
    assert service.state.current_phase == Phase.BIRDSONG


def test_service_can_take_first_real_turn_actions() -> None:
    service = _service()
    safety = 80
    while not service.state.setup_complete and safety > 0:
        service.step()
        safety -= 1
    snap = service.snapshot()
    assert snap.legal_actions, "Game should expose at least 'end_phase'"
