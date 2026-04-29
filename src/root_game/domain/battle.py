"""Battle resolution per Law 4.3.

Battle proceeds in six steps:
  1. Defender may ambush (skipped here; ambush card play is part of the
     attacker action when chosen explicitly).
  2. Before-roll effects.
  3. Roll dice (0-3 each die).
  4. After-roll effects.
  5. Count hits.
  6. Deal hits.

Special cases handled:
  - Alliance Guerrilla War (8.2.2): defender deals higher roll.
  - Vagabond defenseless when no undamaged sword (9.2.4).
  - Defenseless extra hit (4.3.5.II).
  - Score 1 VP per enemy building/token removed.
  - Lone Wanderer: Vagabond pawn cannot be removed (9.2.2).
"""

from dataclasses import dataclass
import random

from .board import Clearing
from .enums import BuildingType, Faction, TokenType
from .faction_state import VagabondState
from .state import GameState


@dataclass
class BattleResult:
    attacker: Faction
    defender: Faction
    clearing_id: int
    attacker_hits_dealt: int = 0
    defender_hits_dealt: int = 0
    attacker_vp: int = 0
    defender_vp: int = 0
    attacker_warriors_lost: int = 0
    defender_warriors_lost: int = 0
    log: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.log is None:
            self.log = []


def resolve_battle(
    state: GameState,
    attacker: Faction,
    defender: Faction,
    clearing_id: int,
    rng: random.Random,
    use_ambush: bool = False,
) -> BattleResult:
    clearing = state.board.clearings[clearing_id]
    result = BattleResult(attacker=attacker, defender=defender, clearing_id=clearing_id)

    if attacker == defender:
        raise ValueError("Attacker and defender must differ.")

    attacker_warriors = clearing.warriors.get(attacker, 0)
    defender_warriors = clearing.warriors.get(defender, 0)
    if defender == Faction.VAGABOND and isinstance(state.players.get(defender), VagabondState):
        # Vagabond uses pawn presence rather than warriors.
        defender_warriors = 1 if clearing.has_vagabond else 0
    if attacker_warriors <= 0:
        raise ValueError(f"Attacker {attacker.name} has no warriors in clearing {clearing_id}.")

    # Step 3: Roll Dice
    high = rng.randint(0, 3)
    low = rng.randint(0, 3)
    if high < low:
        high, low = low, high

    attacker_will_deal = high
    defender_will_deal = low
    # Guerrilla War: Alliance as defender deals high (8.2.2)
    if defender == Faction.ALLIANCE:
        attacker_will_deal, defender_will_deal = low, high
    result.log.append(f"Rolled dice: high={high}, low={low}")

    # Step 3.I: Maximum rolled hits = warriors in clearing
    attacker_will_deal = min(attacker_will_deal, attacker_warriors)
    defender_will_deal = min(defender_will_deal, defender_warriors)

    # Vagabond max rolled hits = undamaged swords (9.2.6)
    if attacker == Faction.VAGABOND:
        vag = state.players[Faction.VAGABOND]
        assert isinstance(vag, VagabondState)
        attacker_will_deal = min(attacker_will_deal, vag.undamaged_swords())
    if defender == Faction.VAGABOND:
        vag = state.players[Faction.VAGABOND]
        assert isinstance(vag, VagabondState)
        defender_will_deal = min(defender_will_deal, vag.undamaged_swords())

    # Step 5.II: Defenseless extra hit
    defenseless_extra = 0
    if defender_warriors == 0:
        defenseless_extra = 1
    if defender == Faction.VAGABOND:
        vag = state.players[Faction.VAGABOND]
        assert isinstance(vag, VagabondState)
        if vag.undamaged_swords() == 0:
            defenseless_extra = 1
    attacker_will_deal += defenseless_extra

    # Ambush (defender, simplified): adds 2 hits to defender if requested
    if use_ambush:
        defender_will_deal += 2

    result.attacker_hits_dealt = attacker_will_deal
    result.defender_hits_dealt = defender_will_deal

    # Step 6: Deal hits
    _apply_hits_to(state, clearing, defender, attacker, attacker_will_deal, result)
    _apply_hits_to(state, clearing, attacker, defender, defender_will_deal, result)

    return result


def _apply_hits_to(
    state: GameState,
    clearing: Clearing,
    target: Faction,
    other: Faction,
    hits: int,
    result: BattleResult,
) -> None:
    """Remove pieces of `target`; warriors first, then buildings/tokens.
    Score 1 VP per enemy building/token removed for `other`.
    """
    remaining = hits
    if remaining <= 0:
        return

    # Warriors first
    warrior_count = clearing.warriors.get(target, 0)
    warriors_removed = min(remaining, warrior_count)
    if warriors_removed > 0:
        clearing.remove_warriors(target, warriors_removed)
        if other == result.attacker:
            result.defender_warriors_lost += warriors_removed
        else:
            result.attacker_warriors_lost += warriors_removed
        remaining -= warriors_removed

    if remaining <= 0:
        return

    # Vagabond takes hits as item damage (handled outside this function).
    if target == Faction.VAGABOND:
        from .faction_state import VagabondState  # local import
        from .enums import ItemState

        vag = state.players[Faction.VAGABOND]
        assert isinstance(vag, VagabondState)
        # Damage one undamaged item per hit, up to capacity.
        for _ in range(remaining):
            damaged = _damage_one_item(vag)
            if not damaged:
                break  # ignore further hits if no items remain
        return

    # Buildings/tokens (each = 1 VP for `other`)
    while remaining > 0 and (clearing.buildings or clearing.tokens):
        if clearing.buildings:
            for idx, (owner, kind) in enumerate(clearing.buildings):
                if owner == target and kind != BuildingType.RUIN:
                    clearing.buildings.pop(idx)
                    state.players[other].victory_points += 1
                    if other == result.attacker:
                        result.attacker_vp += 1
                    else:
                        result.defender_vp += 1
                    remaining -= 1
                    break
            else:
                if remaining <= 0 or not clearing.tokens:
                    break
        if remaining <= 0:
            break
        if clearing.tokens:
            for idx, (owner, _kind) in enumerate(clearing.tokens):
                if owner == target:
                    clearing.tokens.pop(idx)
                    state.players[other].victory_points += 1
                    if other == result.attacker:
                        result.attacker_vp += 1
                    else:
                        result.defender_vp += 1
                    remaining -= 1
                    break
            else:
                break


def _damage_one_item(vag) -> bool:
    """Damage one Vagabond undamaged item. Return True if damaged."""
    from .enums import ItemState

    pools = [
        vag.satchel,
        vag.boots_track,
        vag.swords_track,
        vag.crossbow_track,
        vag.hammer_track,
        vag.teas_track,
        vag.coins_track,
        vag.bags_track,
    ]
    for pool in pools:
        for item in pool:
            if item.state in (ItemState.SATCHEL_FACE_UP, ItemState.TRACK_FACE_UP):
                pool.remove(item)
                vag.damaged.append(
                    type(item)(item=item.item, state=ItemState.DAMAGED_FACE_UP)
                )
                return True
            if item.state in (ItemState.SATCHEL_FACE_DOWN, ItemState.TRACK_FACE_DOWN):
                pool.remove(item)
                vag.damaged.append(
                    type(item)(item=item.item, state=ItemState.DAMAGED_FACE_DOWN)
                )
                return True
    return False
