from root_game.application.controllers import FirstActionController
from root_game.application.service import GameService
from root_game.domain.actions import (
    A_SETUP_CHOOSE_LEADER,
    A_SETUP_PLACE_BASE_AND_OFFICERS,
    A_SETUP_PLACE_KEEP,
    A_SETUP_PLACE_ROOST,
    A_SETUP_PLACE_STARTING_BUILDING,
    A_SETUP_VAGABOND_CHARACTER,
    A_SETUP_VAGABOND_PLACE,
)
from root_game.domain.enums import (
    BuildingType,
    Faction,
    TokenType,
)


def _service() -> GameService:
    factions = [Faction.MARQUISE, Faction.EYRIE, Faction.ALLIANCE, Faction.VAGABOND]
    controllers = {f: FirstActionController() for f in factions}
    return GameService(controllers=controllers, factions=factions, seed=42)


def test_setup_starts_at_marquise_keep_placement() -> None:
    service = _service()
    snap = service.snapshot()
    assert not snap.setup_complete
    assert snap.faction == Faction.MARQUISE
    assert snap.legal_actions, "Setup should expose at least one keep placement"
    assert all(a.action_type == A_SETUP_PLACE_KEEP for a in snap.legal_actions)


def test_setup_walks_through_all_factions() -> None:
    service = _service()
    safety = 50
    while not service.state.setup_complete and safety > 0:
        service.step()
        safety -= 1
    assert service.state.setup_complete
    keep_clearings = [
        cid for cid, c in service.state.board.clearings.items()
        if c.has_token(Faction.MARQUISE, TokenType.KEEP)
    ]
    assert len(keep_clearings) == 1
    keep_cid = keep_clearings[0]
    keep_clearing = service.state.board.clearings[keep_cid]
    assert any(
        owner == Faction.MARQUISE and kind in {
            BuildingType.SAWMILL,
            BuildingType.WORKSHOP,
            BuildingType.RECRUITER,
        }
        for owner, kind in keep_clearing.buildings
    )
    eyrie_corners = [
        cid for cid, c in service.state.board.clearings.items()
        if any(o == Faction.EYRIE and k == BuildingType.ROOST for o, k in c.buildings)
    ]
    assert len(eyrie_corners) == 1


def test_legal_actions_during_setup_are_setup_actions() -> None:
    service = _service()
    snap = service.snapshot()
    setup_action_types = {
        A_SETUP_PLACE_KEEP,
        A_SETUP_PLACE_STARTING_BUILDING,
        A_SETUP_PLACE_ROOST,
        A_SETUP_CHOOSE_LEADER,
        A_SETUP_PLACE_BASE_AND_OFFICERS,
        A_SETUP_VAGABOND_CHARACTER,
        A_SETUP_VAGABOND_PLACE,
    }
    assert all(a.action_type in setup_action_types for a in snap.legal_actions)
