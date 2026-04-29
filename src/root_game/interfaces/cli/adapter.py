"""CLI adapter for the Root base game.

Renders board state and prompts each seat for input. All seats default
to humans on one terminal (hot-seat). The same architecture supports
plugging in bots or a GUI through the Controller protocol.

At any prompt, players can type meta-commands instead of an action number.
Public info (Law 1.2) is available to everyone; private info is only
revealed to its owner.

Private (active player only):
  h / hand        - show the current player's hand
  s / supporters  - Alliance supporters stack (Alliance only)

Public (always available):
  d / decree      - Eyrie decree (face-up tucked cards)
  i / items       - Vagabond items, tracks, damaged, relationships
  b / board       - re-render the board
  p / players     - all players' VP, hand size, items, persistent effects
  u / undo        - undo the most recent action
  ? / help        - show this help
"""

from typing import Sequence

from root_game.application.controllers import CallableController, Controller, UndoRequested
from root_game.application.service import GameService
from root_game.domain.actions import Action
from root_game.domain.enums import (
    DecreeColumn,
    Faction,
    ItemState,
)


def build_human_controllers(
    factions: Sequence[Faction],
    service_ref: list[GameService],
) -> dict[Faction, Controller]:
    """Build a controller per faction wired to a shared GameService reference.

    `service_ref` is a 1-element list so the CLI can fill it after the
    service is constructed (chicken-and-egg: controllers need the service
    to render meta-commands, but the service needs controllers).
    """

    def prompt(faction: Faction, actions: Sequence[Action], label: str) -> int:
        _print_action_menu(faction, actions, label)
        while True:
            choice = input("> ").strip().lower()
            if choice.isdigit():
                option = int(choice)
                if 1 <= option <= len(actions):
                    return option - 1
                print(f"  Please enter a number 1..{len(actions)} or a command.")
                continue
            if choice in {"?", "help"}:
                _print_help()
            elif choice in {"h", "hand"}:
                _print_hand(service_ref[0], faction)
            elif choice in {"s", "supporters"}:
                _print_supporters(service_ref[0], faction)
            elif choice in {"d", "decree"}:
                _print_decree(service_ref[0])
            elif choice in {"i", "items"}:
                _print_items(service_ref[0])
            elif choice in {"b", "board"}:
                _render_board(service_ref[0])
            elif choice in {"p", "players"}:
                _render_players(service_ref[0])
            elif choice in {"u", "undo"}:
                raise UndoRequested()
            else:
                print("  Unknown command. Type ? for help.")
                continue
            _print_action_menu(faction, actions, label)

    return {faction: CallableController(prompt) for faction in factions}


def _print_action_menu(faction: Faction, actions: Sequence[Action], label: str) -> None:
    print(f"\n[{label}] Choose an action (number) or command (h/s/d/i/b/p/u/?):")
    for idx, action in enumerate(actions, 1):
        print(f"  {idx:>2}. {_format_action(action)}")


def _print_help() -> None:
    print("  Private (active player only):")
    print("    h / hand        Show your hand")
    print("    s / supporters  Alliance supporters (Alliance turn only)")
    print("  Public (always):")
    print("    d / decree      Eyrie decree")
    print("    i / items       Vagabond items, tracks, relationships")
    print("    b / board       Re-render the board")
    print("    p / players     Summary of all players")
    print("    u / undo        Undo the most recent action")
    print("    ? / help        Show this help")


def _print_hand(service: GameService, faction: Faction) -> None:
    state = service.state
    hand = state.players[faction].hand
    print(f"\n--- {faction.name} hand ({len(hand)} cards) ---")
    if not hand:
        print("  (empty)")
        return
    for card in hand:
        cost = ", ".join(s.name for s in card.cost.suits) or "no cost"
        effect = card.effect.kind.name
        if card.effect.item:
            effect = f"item {card.effect.item.name} (+{card.effect.points} VP)"
        elif card.effect.persistent_id:
            effect = f"persistent: {card.effect.persistent_id}"
        print(
            f"  #{card.card_id:>3}  {card.name:<25}  suit={card.suit.name:<6} "
            f"kind={card.kind.name:<9} cost=[{cost}] effect={effect}"
        )


def _print_supporters(service: GameService, faction: Faction) -> None:
    if faction != Faction.ALLIANCE:
        print("  Only the Woodland Alliance has a supporters stack.")
        return
    a = service.state.players[Faction.ALLIANCE]
    print(f"\n--- Alliance supporters ({len(a.supporters)}) ---")
    if not a.supporters:
        print("  (empty)")
        return
    for card in a.supporters:
        print(f"  #{card.card_id:>3}  {card.name:<25}  suit={card.suit.name}")


def _print_decree(service: GameService) -> None:
    from root_game.domain.faction_state import EyrieState

    if Faction.EYRIE not in service.state.players:
        print("  Eyrie Dynasties are not in this game.")
        return
    es = service.state.players[Faction.EYRIE]
    assert isinstance(es, EyrieState)
    print(f"\n--- Eyrie decree (leader: {es.leader.name if es.leader else '-'}) ---")
    for col in DecreeColumn:
        items = es.decree[col]
        if not items:
            print(f"  {col.name:<8}: (empty)")
            continue
        labels = [f"{c.name}({c.suit.name[:1]})" for c in items]
        print(f"  {col.name:<8}: {', '.join(labels)}")


def _print_items(service: GameService) -> None:
    from root_game.domain.faction_state import VagabondState

    if Faction.VAGABOND not in service.state.players:
        print("  Vagabond is not in this game.")
        return
    v = service.state.players[Faction.VAGABOND]
    assert isinstance(v, VagabondState)
    location = (
        f"forest {v.pawn_forest}" if v.pawn_forest
        else f"clearing {v.pawn_clearing}" if v.pawn_clearing is not None
        else "off-map"
    )
    print(f"\n--- Vagabond items (character={v.character.name if v.character else '-'}, at {location}) ---")
    print(f"  Satchel : {_format_items(v.satchel)}")
    print(f"  Damaged : {_format_items(v.damaged)}")
    print(f"  Boots   : {_format_items(v.boots_track)}")
    print(f"  Swords  : {_format_items(v.swords_track)}")
    print(f"  Crossbow: {_format_items(v.crossbow_track)}")
    print(f"  Hammer  : {_format_items(v.hammer_track)}")
    print(f"  Tea     : {_format_items(v.teas_track)}")
    print(f"  Coin    : {_format_items(v.coins_track)}")
    print(f"  Bag     : {_format_items(v.bags_track)}")
    print(
        f"  Relationships: "
        + ", ".join(f"{f.name}={r.name}" for f, r in v.relationships.items())
    )


def _format_items(items) -> str:
    if not items:
        return "(empty)"
    parts = []
    for it in items:
        face = "up" if it.state in (
            ItemState.SATCHEL_FACE_UP,
            ItemState.TRACK_FACE_UP,
            ItemState.DAMAGED_FACE_UP,
        ) else "down"
        parts.append(f"{it.item.name}/{face}")
    return ", ".join(parts)


def _format_action(action: Action) -> str:
    if action.payload:
        return f"{action.action_type} {action.payload}"
    return action.action_type


def _render_board(service: GameService) -> None:
    state = service.state
    print("\n=== Board ===")
    for cid, clearing in sorted(state.board.clearings.items()):
        warriors = (
            ", ".join(f"{f.name[:1]}:{n}" for f, n in clearing.warriors.items() if n > 0)
            or "-"
        )
        buildings = (
            ", ".join(
                f"{(o.name[:1] if o else '?')}:{kind.name[:3]}"
                for o, kind in clearing.buildings
            )
            or "-"
        )
        tokens = (
            ", ".join(f"{f.name[:1]}:{t.name[:1]}" for f, t in clearing.tokens)
            or "-"
        )
        ruler = clearing.ruling_faction(eyrie_lords_of_forest=True)
        print(
            f"{cid:>2} [{clearing.suit.name[:1]}] "
            f"slots={clearing.slots} ruler={ruler.name if ruler else '-'} "
            f"W({warriors}) B({buildings}) T({tokens})"
        )


def _render_players(service: GameService) -> None:
    state = service.state
    print("\n=== Players ===")
    for faction, player in state.players.items():
        print(
            f"{faction.name:>9}: VP={player.victory_points:>2} "
            f"hand={len(player.hand)} items={len(player.crafted_items)} "
            f"persistent={sorted(player.persistent_effects) or '-'}"
        )


class CliAdapter:
    def __init__(self, service: GameService) -> None:
        self.service = service

    def run(self) -> None:
        print("Root CLI started. Hot-seat all players. Type ? at any prompt for help.")
        while not self.service.is_finished():
            _render_board(self.service)
            _render_players(self.service)
            self.service.step()
        winner = self.service.state.winner
        print(f"\n=== Winner: {winner.name if winner else 'none'} ===")
