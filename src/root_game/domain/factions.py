"""Faction systems for the Root base game.

Each `FactionSystem` exposes phase hooks (Birdsong/Daylight/Evening) and
generators of legal actions for the rules engine. Faction-specific
edge cases live here to keep the rules engine focused on dispatch.
"""

from __future__ import annotations

from typing import Iterable

from .actions import (
    A_ACTIVATE_DOMINANCE,
    A_ALLIANCE_MIL_OP,
    A_ALLIANCE_MOBILIZE,
    A_ALLIANCE_REVOLT,
    A_ALLIANCE_SPREAD_SYMPATHY,
    A_ALLIANCE_TRAIN,
    A_BATTLE,
    A_CRAFT,
    A_END_PHASE,
    A_EYRIE_ADD_TO_DECREE,
    A_EYRIE_BUILD_ROOST,
    A_EYRIE_RESOLVE_DECREE_CARD,
    A_MARQUISE_BUILD,
    A_MARQUISE_END_MARCH,
    A_MARQUISE_MARCH,
    A_MARQUISE_OVERWORK,
    A_MARQUISE_RECRUIT,
    A_MARQUISE_SPEND_BIRD,
    A_MOVE,
    A_VAGABOND_AID,
    A_VAGABOND_EXPLORE,
    A_VAGABOND_QUEST,
    A_VAGABOND_REPAIR,
    A_VAGABOND_SLIP,
    A_VAGABOND_SPECIAL,
    A_VAGABOND_STRIKE,
    Action,
)
from .enums import (
    BuildingType,
    DecreeColumn,
    EyrieLeader,
    Faction,
    ItemState,
    ItemType,
    Phase,
    Suit,
    TokenType,
    VagabondCharacter,
    VagabondRelationship,
)
from .faction_state import (
    AllianceState,
    EyrieState,
    MarquiseState,
    VagabondState,
)
from .state import GameState


# Helpers ----------------------------------------------------------------

def _factions_in_clearing(state: GameState, clearing_id: int) -> set[Faction]:
    clearing = state.board.clearings[clearing_id]
    enemies = {f for f, n in clearing.warriors.items() if n > 0}
    if clearing.has_vagabond:
        enemies.add(Faction.VAGABOND)
    return enemies


def _ruler(state: GameState, clearing_id: int) -> Faction | None:
    return state.board.clearings[clearing_id].ruling_faction(eyrie_lords_of_forest=True)


def _marquise_build_cost(ms: MarquiseState, building: BuildingType) -> int:
    """Wood cost to build the next building of a given type (Law 6.5.4.III)."""
    track_remaining = {
        BuildingType.SAWMILL: ms.sawmills_remaining,
        BuildingType.WORKSHOP: ms.workshops_remaining,
        BuildingType.RECRUITER: ms.recruiters_remaining,
    }[building]
    placed = 6 - track_remaining
    cost_table = [0, 1, 2, 3, 4]
    return cost_table[min(placed, len(cost_table) - 1)]


def _wood_in(clearing) -> int:
    return sum(
        1
        for owner, kind in clearing.tokens
        if owner == Faction.MARQUISE and kind == TokenType.WOOD
    )


def _connected_marquise_wood(state: GameState, start: int) -> int:
    """Total Marquise wood reachable from `start` via clearings the
    Marquise rules (the start clearing itself does not need to be ruled,
    matching the rules engine's payment helper)."""
    seen: set[int] = set()
    frontier = [start]
    total = 0
    while frontier:
        cid = frontier.pop()
        if cid in seen:
            continue
        seen.add(cid)
        clearing = state.board.clearings[cid]
        if (
            clearing.ruling_faction(eyrie_lords_of_forest=True) != Faction.MARQUISE
            and cid != start
        ):
            continue
        total += _wood_in(clearing)
        for adj in state.board.adjacent_clearings(cid):
            if adj not in seen:
                frontier.append(adj)
    return total


# Marquise --------------------------------------------------------------

class MarquiseSystem:
    faction = Faction.MARQUISE

    @staticmethod
    def begin_birdsong(state: GameState) -> None:
        ms = state.players[Faction.MARQUISE]
        assert isinstance(ms, MarquiseState)
        # 6.4 Place wood at sawmills
        for clearing in state.board.clearings.values():
            sawmills = sum(
                1 for owner, kind in clearing.buildings
                if owner == Faction.MARQUISE and kind == BuildingType.SAWMILL
            )
            for _ in range(sawmills):
                if ms.wood_in_supply <= 0:
                    break
                clearing.place_token(Faction.MARQUISE, TokenType.WOOD)
                ms.wood_in_supply -= 1

    @staticmethod
    def begin_daylight(state: GameState) -> None:
        ms = state.players[Faction.MARQUISE]
        assert isinstance(ms, MarquiseState)
        # Up to 3 actions plus 1 per bird card spent (6.5)
        ms.actions_remaining = 3
        ms.march_moves_remaining = 0
        ms.recruit_used_this_turn = False
        ms.crafting_used_workshops = set()

    @staticmethod
    def end_evening(state: GameState) -> None:
        ms = state.players[Faction.MARQUISE]
        assert isinstance(ms, MarquiseState)
        # Draw 1 card + uncovered draw bonuses (simplified: just 1 card here)
        state.draw_card(Faction.MARQUISE)
        # Discard down to 5
        while len(ms.hand) > 5:
            state.discard(ms.hand.pop())

    @staticmethod
    def legal_actions(state: GameState) -> list[Action]:
        ms = state.players[Faction.MARQUISE]
        assert isinstance(ms, MarquiseState)
        actions: list[Action] = [Action(Faction.MARQUISE, A_END_PHASE)]
        if state.current_phase != Phase.DAYLIGHT:
            return actions

        # If a March is in progress, only show move options + end_march.
        if ms.march_moves_remaining > 0:
            actions = [
                Action(Faction.MARQUISE, A_MARQUISE_END_MARCH)
            ]
            for clearing in state.board.clearings.values():
                cid = clearing.clearing_id
                if clearing.warriors.get(Faction.MARQUISE, 0) <= 0:
                    continue
                for adjacent in state.board.adjacent_clearings(cid):
                    if (
                        _ruler(state, cid) == Faction.MARQUISE
                        or _ruler(state, adjacent) == Faction.MARQUISE
                    ):
                        actions.append(
                            Action(
                                Faction.MARQUISE,
                                A_MOVE,
                                {"from": cid, "to": adjacent, "count": 1},
                            )
                        )
            return actions

        if ms.actions_remaining <= 0:
            return actions

        # Battle / March / Recruit / Build / Overwork
        marching_possible = False
        for clearing in state.board.clearings.values():
            cid = clearing.clearing_id
            if clearing.warriors.get(Faction.MARQUISE, 0) > 0:
                for adjacent in state.board.adjacent_clearings(cid):
                    if (
                        _ruler(state, cid) == Faction.MARQUISE
                        or _ruler(state, adjacent) == Faction.MARQUISE
                    ):
                        marching_possible = True
                        break
                # Battle
                for enemy in _factions_in_clearing(state, cid):
                    if enemy != Faction.MARQUISE:
                        actions.append(
                            Action(
                                Faction.MARQUISE,
                                A_BATTLE,
                                {"clearing": cid, "defender": enemy.name},
                            )
                        )
            # Build (Law 6.5.4: choose any clearing you rule and pay wood)
            if _ruler(state, cid) == Faction.MARQUISE and clearing.open_slots() > 0:
                reachable_wood = _connected_marquise_wood(state, cid)
                track_remaining = {
                    BuildingType.SAWMILL: ms.sawmills_remaining,
                    BuildingType.WORKSHOP: ms.workshops_remaining,
                    BuildingType.RECRUITER: ms.recruiters_remaining,
                }
                for kind in (
                    BuildingType.SAWMILL,
                    BuildingType.WORKSHOP,
                    BuildingType.RECRUITER,
                ):
                    if track_remaining[kind] <= 0:
                        continue
                    if reachable_wood < _marquise_build_cost(ms, kind):
                        continue
                    actions.append(
                        Action(
                            Faction.MARQUISE,
                            A_MARQUISE_BUILD,
                            {"clearing": cid, "building": kind.name},
                        )
                    )
            # Overwork (Law 6.5.5: spend matching card to place wood at a sawmill)
            if clearing.has_building(BuildingType.SAWMILL, Faction.MARQUISE):
                for card in ms.hand:
                    if card.suit == clearing.suit or card.suit == Suit.BIRD:
                        actions.append(
                            Action(
                                Faction.MARQUISE,
                                A_MARQUISE_OVERWORK,
                                {"clearing": cid, "card": card.card_id},
                            )
                        )
        if marching_possible:
            actions.append(Action(Faction.MARQUISE, A_MARQUISE_MARCH))
        # Recruit (once per turn)
        if not ms.recruit_used_this_turn:
            recruiters_present = any(
                clearing.has_building(BuildingType.RECRUITER, Faction.MARQUISE)
                for clearing in state.board.clearings.values()
            )
            if recruiters_present:
                actions.append(Action(Faction.MARQUISE, A_MARQUISE_RECRUIT))
        # Spend bird card for an extra action
        for card in ms.hand:
            if card.suit == Suit.BIRD:
                actions.append(
                    Action(Faction.MARQUISE, A_MARQUISE_SPEND_BIRD, {"card": card.card_id})
                )
        return actions


# Eyrie ------------------------------------------------------------------

class EyrieSystem:
    faction = Faction.EYRIE

    @staticmethod
    def begin_birdsong(state: GameState) -> None:
        es = state.players[Faction.EYRIE]
        assert isinstance(es, EyrieState)
        # 7.5.1 reset per-Birdsong "Add to Decree" counters
        es.decree_adds_this_birdsong = 0
        es.decree_bird_added_this_birdsong = False
        # 7.4.1 Emergency Orders
        if not es.hand:
            state.draw_card(Faction.EYRIE)
        # 7.4.3 New Roost (handled lazily; if no roosts on map, allow placement)
        roosts = sum(
            1
            for clearing in state.board.clearings.values()
            for owner, kind in clearing.buildings
            if owner == Faction.EYRIE and kind == BuildingType.ROOST
        )
        if roosts == 0 and es.roosts_remaining > 0:
            target = min(
                state.board.clearings.values(),
                key=lambda c: c.warriors.get(Faction.EYRIE, 0) + sum(c.warriors.values()),
            )
            if target.open_slots() > 0:
                target.place_building(Faction.EYRIE, BuildingType.ROOST)
                es.roosts_remaining -= 1
                target.add_warriors(Faction.EYRIE, min(3, es.warriors_in_supply))
                es.warriors_in_supply -= min(3, es.warriors_in_supply)

    @staticmethod
    def end_evening(state: GameState) -> None:
        es = state.players[Faction.EYRIE]
        assert isinstance(es, EyrieState)
        # 7.6.1 Score points based on roosts (simplified curve)
        roosts_on_map = sum(
            1
            for clearing in state.board.clearings.values()
            for owner, kind in clearing.buildings
            if owner == Faction.EYRIE and kind == BuildingType.ROOST
        )
        scoring = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 4, 7: 5}
        es.victory_points += scoring.get(roosts_on_map, 0)
        state.draw_card(Faction.EYRIE)
        while len(es.hand) > 5:
            state.discard(es.hand.pop())

    @staticmethod
    def legal_actions(state: GameState) -> list[Action]:
        es = state.players[Faction.EYRIE]
        assert isinstance(es, EyrieState)
        actions: list[Action] = [Action(Faction.EYRIE, A_END_PHASE)]
        if state.current_phase == Phase.BIRDSONG:
            # Law 7.5.1: add up to 2 cards to the Decree per Birdsong, with
            # at most one of them being a bird card.
            if es.decree_adds_this_birdsong < 2:
                for col in DecreeColumn:
                    for card in es.hand:
                        if (
                            card.suit == Suit.BIRD
                            and es.decree_bird_added_this_birdsong
                        ):
                            continue
                        actions.append(
                            Action(
                                Faction.EYRIE,
                                A_EYRIE_ADD_TO_DECREE,
                                {"column": col.name, "card": card.card_id},
                            )
                        )
        if state.current_phase == Phase.DAYLIGHT:
            # Resolve decree (presented as 'resolve next decree slot' actions)
            for col, cards in es.decree.items():
                if cards:
                    actions.append(
                        Action(
                            Faction.EYRIE,
                            A_EYRIE_RESOLVE_DECREE_CARD,
                            {"column": col.name},
                        )
                    )
            # Build a roost in a ruled clearing matching a hand card
            for clearing in state.board.clearings.values():
                if (
                    _ruler(state, clearing.clearing_id) == Faction.EYRIE
                    and clearing.open_slots() > 0
                ):
                    actions.append(
                        Action(
                            Faction.EYRIE,
                            A_EYRIE_BUILD_ROOST,
                            {"clearing": clearing.clearing_id},
                        )
                    )
        return actions


# Alliance ---------------------------------------------------------------

class AllianceSystem:
    faction = Faction.ALLIANCE

    @staticmethod
    def begin_birdsong(state: GameState) -> None:
        # No automatic actions; player chooses revolt/spread.
        pass

    @staticmethod
    def begin_daylight(state: GameState) -> None:
        pass

    @staticmethod
    def begin_evening(state: GameState) -> None:
        a = state.players[Faction.ALLIANCE]
        assert isinstance(a, AllianceState)
        a.officer_actions_remaining = a.officers

    @staticmethod
    def end_evening(state: GameState) -> None:
        a = state.players[Faction.ALLIANCE]
        assert isinstance(a, AllianceState)
        state.draw_card(Faction.ALLIANCE)
        while len(a.hand) > 5:
            state.discard(a.hand.pop())

    @staticmethod
    def legal_actions(state: GameState) -> list[Action]:
        a = state.players[Faction.ALLIANCE]
        assert isinstance(a, AllianceState)
        actions: list[Action] = [Action(Faction.ALLIANCE, A_END_PHASE)]
        if state.current_phase == Phase.BIRDSONG:
            # Revolt: sympathetic clearing without a base whose suit matches a base
            for clearing in state.board.clearings.values():
                if not clearing.has_token(Faction.ALLIANCE, TokenType.SYMPATHY):
                    continue
                if any(
                    owner == Faction.ALLIANCE and kind in {
                        BuildingType.BASE_FOX,
                        BuildingType.BASE_RABBIT,
                        BuildingType.BASE_MOUSE,
                    }
                    for owner, kind in clearing.buildings
                ):
                    continue
                actions.append(
                    Action(
                        Faction.ALLIANCE,
                        A_ALLIANCE_REVOLT,
                        {"clearing": clearing.clearing_id},
                    )
                )
            # Spread sympathy
            for clearing in state.board.clearings.values():
                if clearing.has_token(Faction.ALLIANCE, TokenType.SYMPATHY):
                    continue
                adjacent_sympathetic = any(
                    state.board.clearings[adj].has_token(Faction.ALLIANCE, TokenType.SYMPATHY)
                    for adj in state.board.adjacent_clearings(clearing.clearing_id)
                )
                first_token = a.sympathy_tokens_remaining == 10
                if adjacent_sympathetic or first_token:
                    actions.append(
                        Action(
                            Faction.ALLIANCE,
                            A_ALLIANCE_SPREAD_SYMPATHY,
                            {"clearing": clearing.clearing_id},
                        )
                    )
        if state.current_phase == Phase.DAYLIGHT:
            # Mobilize / Train
            for card in a.hand:
                actions.append(
                    Action(Faction.ALLIANCE, A_ALLIANCE_MOBILIZE, {"card": card.card_id})
                )
            base_suits_on_map = {
                BuildingType.BASE_FOX: Suit.FOX,
                BuildingType.BASE_RABBIT: Suit.RABBIT,
                BuildingType.BASE_MOUSE: Suit.MOUSE,
            }
            for card in a.hand:
                for base in a.bases_on_map:
                    if base in base_suits_on_map and (
                        card.suit == base_suits_on_map[base] or card.suit == Suit.BIRD
                    ):
                        actions.append(
                            Action(
                                Faction.ALLIANCE,
                                A_ALLIANCE_TRAIN,
                                {"card": card.card_id, "base": base.name},
                            )
                        )
        if state.current_phase == Phase.EVENING and a.officer_actions_remaining > 0:
            actions.append(Action(Faction.ALLIANCE, A_ALLIANCE_MIL_OP, {"action": "move"}))
            actions.append(Action(Faction.ALLIANCE, A_ALLIANCE_MIL_OP, {"action": "battle"}))
            actions.append(Action(Faction.ALLIANCE, A_ALLIANCE_MIL_OP, {"action": "recruit"}))
            actions.append(Action(Faction.ALLIANCE, A_ALLIANCE_MIL_OP, {"action": "organize"}))
        return actions


# Vagabond --------------------------------------------------------------

class VagabondSystem:
    faction = Faction.VAGABOND

    @staticmethod
    def begin_birdsong(state: GameState) -> None:
        v = state.players[Faction.VAGABOND]
        assert isinstance(v, VagabondState)
        # 9.4.1 Refresh up to 3 + tea bonus
        refreshes = 3 + sum(
            1 for it in v.teas_track if it.state == ItemState.TRACK_FACE_UP
        )
        _refresh_items(v, refreshes)

    @staticmethod
    def end_evening(state: GameState) -> None:
        v = state.players[Faction.VAGABOND]
        assert isinstance(v, VagabondState)
        # 9.6.1 Rest if in forest
        if v.pawn_forest is not None:
            for it in list(v.damaged):
                v.damaged.remove(it)
                v.add_item(it.item)
        # 9.6.2 Draw 1 + per coin face-up
        draw_count = 1 + sum(
            1 for it in v.coins_track if it.state == ItemState.TRACK_FACE_UP
        )
        for _ in range(draw_count):
            state.draw_card(Faction.VAGABOND)
        # 9.6.3 Discard down to 5
        while len(v.hand) > 5:
            state.discard(v.hand.pop())
        # 9.6.4 Item capacity
        capacity = v.item_capacity()
        excess = max(0, len(v.satchel) + len(v.damaged) - capacity)
        for _ in range(excess):
            if v.damaged:
                v.damaged.pop()
            elif v.satchel:
                v.satchel.pop()

    @staticmethod
    def legal_actions(state: GameState) -> list[Action]:
        v = state.players[Faction.VAGABOND]
        assert isinstance(v, VagabondState)
        actions: list[Action] = [Action(Faction.VAGABOND, A_END_PHASE)]
        if state.current_phase == Phase.BIRDSONG:
            actions.extend(_vagabond_slip_actions(state, v))
        if state.current_phase == Phase.DAYLIGHT and v.pawn_clearing is not None:
            cid = v.pawn_clearing
            clearing = state.board.clearings[cid]
            # Move
            for adjacent in state.board.adjacent_clearings(cid):
                actions.append(
                    Action(Faction.VAGABOND, A_MOVE, {"from": cid, "to": adjacent})
                )
            # Battle
            for enemy in _factions_in_clearing(state, cid):
                if enemy != Faction.VAGABOND:
                    actions.append(
                        Action(
                            Faction.VAGABOND,
                            A_BATTLE,
                            {"clearing": cid, "defender": enemy.name},
                        )
                    )
            # Strike
            for enemy in _factions_in_clearing(state, cid):
                if enemy != Faction.VAGABOND:
                    actions.append(
                        Action(
                            Faction.VAGABOND,
                            A_VAGABOND_STRIKE,
                            {"clearing": cid, "defender": enemy.name},
                        )
                    )
            # Aid
            for enemy in _factions_in_clearing(state, cid):
                if enemy == Faction.VAGABOND:
                    continue
                for card in v.hand:
                    if card.suit == clearing.suit or card.suit == Suit.BIRD:
                        actions.append(
                            Action(
                                Faction.VAGABOND,
                                A_VAGABOND_AID,
                                {
                                    "clearing": cid,
                                    "faction": enemy.name,
                                    "card": card.card_id,
                                },
                            )
                        )
            # Explore (ruin in clearing)
            if any(kind == BuildingType.RUIN for _, kind in clearing.buildings):
                actions.append(Action(Faction.VAGABOND, A_VAGABOND_EXPLORE, {"clearing": cid}))
            # Quest
            actions.append(Action(Faction.VAGABOND, A_VAGABOND_QUEST, {"clearing": cid}))
            # Repair
            if v.damaged:
                actions.append(Action(Faction.VAGABOND, A_VAGABOND_REPAIR))
            # Special action (character-specific stub)
            actions.append(Action(Faction.VAGABOND, A_VAGABOND_SPECIAL))
        return actions


def _refresh_items(v: VagabondState, count: int) -> None:
    pools = [
        v.satchel,
        v.boots_track,
        v.swords_track,
        v.crossbow_track,
        v.hammer_track,
        v.teas_track,
        v.coins_track,
        v.bags_track,
    ]
    refreshed = 0
    for pool in pools:
        if refreshed >= count:
            break
        for item in pool:
            if item.state == ItemState.SATCHEL_FACE_DOWN:
                item.state = ItemState.SATCHEL_FACE_UP
                refreshed += 1
            elif item.state == ItemState.TRACK_FACE_DOWN:
                item.state = ItemState.TRACK_FACE_UP
                refreshed += 1
            if refreshed >= count:
                break


def _vagabond_slip_actions(state: GameState, v: VagabondState) -> list[Action]:
    moves: list[Action] = []
    if v.pawn_clearing is not None:
        for adj in state.board.adjacent_clearings(v.pawn_clearing):
            moves.append(
                Action(
                    Faction.VAGABOND,
                    A_VAGABOND_SLIP,
                    {"from_clearing": v.pawn_clearing, "to_clearing": adj},
                )
            )
        for forest in state.board.forests_adjacent_to_clearing(v.pawn_clearing):
            moves.append(
                Action(
                    Faction.VAGABOND,
                    A_VAGABOND_SLIP,
                    {"from_clearing": v.pawn_clearing, "to_forest": forest},
                )
            )
    if v.pawn_forest is not None:
        for cid in state.board.clearings_in_forest(v.pawn_forest):
            moves.append(
                Action(
                    Faction.VAGABOND,
                    A_VAGABOND_SLIP,
                    {"from_forest": v.pawn_forest, "to_clearing": cid},
                )
            )
    return moves
