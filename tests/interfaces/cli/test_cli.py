from root_game.application.controllers import FirstActionController
from root_game.application.service import GameService
from root_game.domain.enums import Faction
from root_game.interfaces.cli.adapter import (
    CliAdapter,
    _format_action,
    _format_items,
    build_human_controllers,
)


def test_cli_can_format_action_payloads() -> None:
    factions = [Faction.MARQUISE, Faction.EYRIE, Faction.ALLIANCE, Faction.VAGABOND]
    service = GameService(
        controllers={f: FirstActionController() for f in factions},
        factions=factions,
        seed=7,
    )
    snap = service.snapshot()
    adapter = CliAdapter(service)
    assert adapter is not None
    rendered = _format_action(snap.legal_actions[0])
    assert isinstance(rendered, str) and rendered


def test_build_human_controllers_returns_one_per_faction() -> None:
    factions = [Faction.MARQUISE, Faction.EYRIE, Faction.ALLIANCE, Faction.VAGABOND]
    service_ref: list[GameService] = []
    controllers = build_human_controllers(factions, service_ref)
    assert set(controllers.keys()) == set(factions)


def test_format_items_handles_empty_and_populated() -> None:
    assert _format_items([]) == "(empty)"
