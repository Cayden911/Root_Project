"""Entrypoint for the Root CLI."""

from root_game.application.service import GameService
from root_game.domain.enums import Faction
from root_game.interfaces.cli.adapter import CliAdapter, build_human_controllers


def main() -> None:
    factions = [Faction.MARQUISE, Faction.EYRIE, Faction.ALLIANCE, Faction.VAGABOND]
    service_ref: list[GameService] = []
    controllers = build_human_controllers(factions, service_ref)
    service = GameService(controllers=controllers, factions=factions)
    service_ref.append(service)
    cli = CliAdapter(service)
    cli.run()


if __name__ == "__main__":
    main()
