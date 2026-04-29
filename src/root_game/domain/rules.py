"""Rules engine for the Root base game.

The engine is the single mutator of state. It validates an `Action`
against the current phase/seat, dispatches to the proper faction system
(or shared handler), runs side effects, and checks victory conditions.
"""

from __future__ import annotations

import random
from typing import Sequence

from .actions import (
    A_ACTIVATE_DOMINANCE,
    A_ALLIANCE_MIL_OP,
    A_ALLIANCE_MOBILIZE,
    A_ALLIANCE_REVOLT,
    A_ALLIANCE_SPREAD_SYMPATHY,
    A_ALLIANCE_TRAIN,
    A_BATTLE,
    A_CRAFT,
    A_DRAW,
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
    A_SETUP_CHOOSE_LEADER,
    A_SETUP_DONE,
    A_SETUP_PLACE_BASE_AND_OFFICERS,
    A_SETUP_PLACE_KEEP,
    A_SETUP_PLACE_ROOST,
    A_SETUP_PLACE_STARTING_BUILDING,
    A_SETUP_VAGABOND_CHARACTER,
    A_SETUP_VAGABOND_PLACE,
    A_VAGABOND_AID,
    A_VAGABOND_EXPLORE,
    A_VAGABOND_QUEST,
    A_VAGABOND_REPAIR,
    A_VAGABOND_SLIP,
    A_VAGABOND_SPECIAL,
    A_VAGABOND_STRIKE,
    Action,
)
from .battle import resolve_battle
from .cards import Card
from .enums import (
    CORNER_CLEARINGS,
    OPPOSITE_CORNERS,
    BuildingType,
    CardKind,
    CraftEffectType,
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
    VagabondItem,
    VagabondState,
)
from .factions import (
    AllianceSystem,
    EyrieSystem,
    MarquiseSystem,
    VagabondSystem,
)
from .state import GameState


VICTORY_THRESHOLD = 30


class RulesEngine:
    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    # Dispatch -----------------------------------------------------------
    def legal_actions(self, state: GameState, faction: Faction) -> list[Action]:
        if state.winner is not None:
            return []
        if faction != state.current_faction:
            return []
        if not state.setup_complete:
            return self._setup_legal_actions(state, faction)
        actions: list[Action] = []
        if faction == Faction.MARQUISE:
            actions.extend(MarquiseSystem.legal_actions(state))
        elif faction == Faction.EYRIE:
            actions.extend(EyrieSystem.legal_actions(state))
        elif faction == Faction.ALLIANCE:
            actions.extend(AllianceSystem.legal_actions(state))
        elif faction == Faction.VAGABOND:
            actions.extend(VagabondSystem.legal_actions(state))
        # Crafting (Daylight) - shared helper
        if state.current_phase == Phase.DAYLIGHT:
            actions.extend(self._craft_actions(state, faction))
            actions.extend(self._dominance_actions(state, faction))
        return actions

    def execute(self, state: GameState, action: Action) -> None:
        if state.winner is not None:
            raise ValueError("Game already finished.")
        if action.actor != state.current_faction:
            raise ValueError(f"Not {action.actor.name}'s turn.")
        if not state.setup_complete:
            self._execute_setup(state, action)
            self._check_victory(state)
            return
        handler = _DISPATCH.get(action.action_type)
        if handler is None:
            raise ValueError(f"Unknown action type: {action.action_type}")
        handler(self, state, action)
        self._check_victory(state)

    # Setup -------------------------------------------------------------
    def _setup_legal_actions(self, state: GameState, faction: Faction) -> list[Action]:
        # Setup steps (sequential per Law 5.1.7):
        #   0: Marquise places keep in a corner
        #   1: Marquise places 3 starting buildings (keep clearing or adjacent)
        #   2: Marquise garrison (auto)
        #   3: Eyrie places roost in opposite corner
        #   4: Eyrie chooses leader
        #   5: Alliance done (auto, draws supporters)
        #   6: Vagabond chooses character
        #   7: Vagabond places pawn in a forest
        #   8: setup done
        if faction == Faction.MARQUISE and state.setup_step == 0:
            ms = state.players[Faction.MARQUISE]
            return [
                Action(faction, A_SETUP_PLACE_KEEP, {"clearing": cid})
                for cid in CORNER_CLEARINGS
                if state.board.clearings[cid].open_slots() > 0
            ]
        if faction == Faction.MARQUISE and state.setup_step == 1:
            ms = state.players[Faction.MARQUISE]
            assert isinstance(ms, MarquiseState)
            keep_cid = self._marquise_keep_clearing(state)
            adjacent = state.board.adjacent_clearings(keep_cid) if keep_cid else []
            valid_cids = []
            if keep_cid:
                valid_cids = [keep_cid] + adjacent
            options: list[Action] = []
            if not ms.starting_buildings_remaining:
                options.append(Action(faction, A_SETUP_DONE))
                return options
            for cid in valid_cids:
                if state.board.clearings[cid].open_slots() <= 0:
                    continue
                for kind in ms.starting_buildings_remaining:
                    options.append(
                        Action(
                            faction,
                            A_SETUP_PLACE_STARTING_BUILDING,
                            {"clearing": cid, "building": kind.name},
                        )
                    )
            return options
        if faction == Faction.EYRIE and state.setup_step == 3:
            opposite_corners = self._eyrie_corner_options(state)
            return [
                Action(faction, A_SETUP_PLACE_ROOST, {"clearing": cid})
                for cid in opposite_corners
            ]
        if faction == Faction.EYRIE and state.setup_step == 4:
            es = state.players[Faction.EYRIE]
            assert isinstance(es, EyrieState)
            return [
                Action(faction, A_SETUP_CHOOSE_LEADER, {"leader": leader.name})
                for leader in es.available_leaders
            ]
        if faction == Faction.ALLIANCE and state.setup_step == 5:
            return [Action(faction, A_SETUP_PLACE_BASE_AND_OFFICERS)]
        if faction == Faction.VAGABOND and state.setup_step == 6:
            return [
                Action(faction, A_SETUP_VAGABOND_CHARACTER, {"character": char.name})
                for char in VagabondCharacter
            ]
        if faction == Faction.VAGABOND and state.setup_step == 7:
            return [
                Action(faction, A_SETUP_VAGABOND_PLACE, {"forest": fid})
                for fid in state.board.forests.keys()
            ]
        return [Action(faction, A_SETUP_DONE)]

    def _execute_setup(self, state: GameState, action: Action) -> None:
        if action.action_type == A_SETUP_PLACE_KEEP:
            ms = state.players[Faction.MARQUISE]
            assert isinstance(ms, MarquiseState)
            cid = int(action.payload["clearing"])
            state.board.clearings[cid].place_token(Faction.MARQUISE, TokenType.KEEP)
            ms.keep_placed = True
            self._marquise_garrison(state, cid)
            state.setup_step = 1
            return
        if action.action_type == A_SETUP_PLACE_STARTING_BUILDING:
            ms = state.players[Faction.MARQUISE]
            assert isinstance(ms, MarquiseState)
            cid = int(action.payload["clearing"])
            building = BuildingType[action.payload["building"]]
            state.board.clearings[cid].place_building(Faction.MARQUISE, building)
            ms.starting_buildings_remaining.remove(building)
            if building == BuildingType.SAWMILL:
                ms.sawmills_remaining -= 1
            elif building == BuildingType.WORKSHOP:
                ms.workshops_remaining -= 1
            elif building == BuildingType.RECRUITER:
                ms.recruiters_remaining -= 1
            if not ms.starting_buildings_remaining:
                state.setup_step = 3
                state.current_turn_index = self._index_of(state, Faction.EYRIE)
            return
        if action.action_type == A_SETUP_PLACE_ROOST:
            es = state.players[Faction.EYRIE]
            assert isinstance(es, EyrieState)
            cid = int(action.payload["clearing"])
            state.board.clearings[cid].place_building(Faction.EYRIE, BuildingType.ROOST)
            state.board.clearings[cid].add_warriors(Faction.EYRIE, 6)
            es.roosts_remaining -= 1
            es.warriors_in_supply -= 6
            state.setup_step = 4
            return
        if action.action_type == A_SETUP_CHOOSE_LEADER:
            es = state.players[Faction.EYRIE]
            assert isinstance(es, EyrieState)
            leader = EyrieLeader[action.payload["leader"]]
            es.leader = leader
            es.available_leaders.remove(leader)
            self._tuck_loyal_viziers(es, leader)
            state.setup_step = 5
            state.current_turn_index = self._index_of(state, Faction.ALLIANCE)
            return
        if action.action_type == A_SETUP_PLACE_BASE_AND_OFFICERS:
            a = state.players[Faction.ALLIANCE]
            assert isinstance(a, AllianceState)
            for _ in range(3):
                card = state.draw_card(Faction.ALLIANCE)
                if card is None:
                    break
                a.hand.remove(card)
                a.add_supporter(card)
            state.setup_step = 6
            if Faction.VAGABOND in state.players:
                state.current_turn_index = self._index_of(state, Faction.VAGABOND)
            else:
                state.setup_step = 8
                state.setup_complete = True
                state.current_turn_index = 0
                state.turn_count = 1
                self._begin_birdsong(state, state.current_faction)
            return
        if action.action_type == A_SETUP_VAGABOND_CHARACTER:
            v = state.players[Faction.VAGABOND]
            assert isinstance(v, VagabondState)
            character = VagabondCharacter[action.payload["character"]]
            v.character = character
            for item in self._starting_items_for(character):
                v.add_item(item)
            state.setup_step = 7
            return
        if action.action_type == A_SETUP_VAGABOND_PLACE:
            v = state.players[Faction.VAGABOND]
            assert isinstance(v, VagabondState)
            forest = action.payload["forest"]
            v.pawn_forest = forest
            state.setup_step = 8
            state.setup_complete = True
            state.current_turn_index = 0
            state.turn_count = 1
            self._begin_birdsong(state, state.current_faction)
            return
        if action.action_type == A_SETUP_DONE:
            state.setup_step += 1
            if state.setup_step >= 8:
                state.setup_complete = True
                state.current_turn_index = 0
                state.turn_count = 1
            return
        raise ValueError(f"Unknown setup action: {action.action_type}")

    def _marquise_keep_clearing(self, state: GameState) -> int | None:
        for cid, clearing in state.board.clearings.items():
            if clearing.has_token(Faction.MARQUISE, TokenType.KEEP):
                return cid
        return None

    def _marquise_garrison(self, state: GameState, keep_cid: int) -> None:
        ms = state.players[Faction.MARQUISE]
        assert isinstance(ms, MarquiseState)
        opposite = OPPOSITE_CORNERS.get(keep_cid)
        for cid, clearing in state.board.clearings.items():
            if cid == opposite:
                continue
            clearing.add_warriors(Faction.MARQUISE, 1)
            ms.warriors_in_supply -= 1
        # Also place starting warrior in the keep clearing (Garrison covers it).
        state.append_log(
            f"Marquise garrison placed; opposite corner {opposite} left empty."
        )

    def _eyrie_corner_options(self, state: GameState) -> list[int]:
        used: set[int] = set()
        for cid, clearing in state.board.clearings.items():
            if clearing.has_token(Faction.MARQUISE, TokenType.KEEP):
                used.add(cid)
        candidates = [cid for cid in CORNER_CLEARINGS if cid not in used]
        # Prefer diagonally opposite from Marquise keep
        keep_cid = next(
            (cid for cid, clearing in state.board.clearings.items()
             if clearing.has_token(Faction.MARQUISE, TokenType.KEEP)),
            None,
        )
        if keep_cid and OPPOSITE_CORNERS.get(keep_cid) in candidates:
            return [OPPOSITE_CORNERS[keep_cid]]
        return candidates

    def _tuck_loyal_viziers(self, es: EyrieState, leader: EyrieLeader) -> None:
        leader_columns = {
            EyrieLeader.BUILDER: (DecreeColumn.RECRUIT, DecreeColumn.MOVE),
            EyrieLeader.CHARISMATIC: (DecreeColumn.RECRUIT, DecreeColumn.BATTLE),
            EyrieLeader.COMMANDER: (DecreeColumn.MOVE, DecreeColumn.BATTLE),
            EyrieLeader.DESPOT: (DecreeColumn.MOVE, DecreeColumn.BUILD),
        }
        cols = leader_columns[leader]
        for col in cols:
            es.decree[col].append(_LOYAL_VIZIER)

    def _starting_items_for(self, character: VagabondCharacter) -> list[ItemType]:
        if character == VagabondCharacter.THIEF:
            return [ItemType.BOOT, ItemType.TORCH, ItemType.SWORD, ItemType.TEA]
        if character == VagabondCharacter.TINKER:
            return [ItemType.BOOT, ItemType.TORCH, ItemType.HAMMER, ItemType.BAG]
        if character == VagabondCharacter.RANGER:
            return [ItemType.BOOT, ItemType.TORCH, ItemType.SWORD, ItemType.CROSSBOW]
        return []

    def _index_of(self, state: GameState, faction: Faction) -> int:
        return state.turn_order.index(faction)

    # Action handlers ----------------------------------------------------
    def _handle_end_phase(self, state: GameState, action: Action) -> None:
        # Run end-of-phase / start-of-next-phase hooks
        prev_phase = state.current_phase
        prev_faction = state.current_faction
        # End-of-phase scoring
        if prev_phase == Phase.EVENING:
            self._end_of_evening(state, prev_faction)
        state.advance_phase()
        # Start-of-phase hooks
        new_faction = state.current_faction
        if state.current_phase == Phase.BIRDSONG:
            self._begin_birdsong(state, new_faction)
        elif state.current_phase == Phase.DAYLIGHT:
            self._begin_daylight(state, new_faction)
        elif state.current_phase == Phase.EVENING:
            self._begin_evening(state, new_faction)

    def _begin_birdsong(self, state: GameState, faction: Faction) -> None:
        if faction == Faction.MARQUISE:
            MarquiseSystem.begin_birdsong(state)
        elif faction == Faction.EYRIE:
            EyrieSystem.begin_birdsong(state)
        elif faction == Faction.ALLIANCE:
            AllianceSystem.begin_birdsong(state)
        elif faction == Faction.VAGABOND:
            VagabondSystem.begin_birdsong(state)

    def _begin_daylight(self, state: GameState, faction: Faction) -> None:
        if faction == Faction.MARQUISE:
            MarquiseSystem.begin_daylight(state)
        elif faction == Faction.ALLIANCE:
            AllianceSystem.begin_daylight(state)

    def _begin_evening(self, state: GameState, faction: Faction) -> None:
        if faction == Faction.ALLIANCE:
            AllianceSystem.begin_evening(state)

    def _end_of_evening(self, state: GameState, faction: Faction) -> None:
        if faction == Faction.MARQUISE:
            MarquiseSystem.end_evening(state)
        elif faction == Faction.EYRIE:
            EyrieSystem.end_evening(state)
        elif faction == Faction.ALLIANCE:
            AllianceSystem.end_evening(state)
        elif faction == Faction.VAGABOND:
            VagabondSystem.end_evening(state)

    def _handle_move(self, state: GameState, action: Action) -> None:
        faction = action.actor
        source = int(action.payload["from"])
        target = int(action.payload["to"])
        count = int(action.payload.get("count", 1))
        if not state.board.is_connected(source, target):
            raise ValueError("Source and target are not adjacent.")
        # Movement rules per faction
        if faction == Faction.VAGABOND:
            v = state.players[Faction.VAGABOND]
            assert isinstance(v, VagabondState)
            v.pawn_clearing = target
            state.board.clearings[source].has_vagabond = False
            state.board.clearings[target].has_vagabond = True
            self._vagabond_exhaust_item(v, ItemType.BOOT)
            return
        rules_origin = state.board.clearings[source].ruling_faction(eyrie_lords_of_forest=True)
        rules_target = state.board.clearings[target].ruling_faction(eyrie_lords_of_forest=True)
        if faction not in (rules_origin, rules_target):
            raise ValueError("To move, you must rule origin or destination (Law 4.2.1).")
        clearing_src = state.board.clearings[source]
        clearing_dst = state.board.clearings[target]
        clearing_src.remove_warriors(faction, count)
        clearing_dst.add_warriors(faction, count)
        if faction == Faction.MARQUISE:
            ms = state.players[Faction.MARQUISE]
            assert isinstance(ms, MarquiseState)
            if ms.march_moves_remaining > 0:
                # Movement happens within an active March (Law 6.5.2).
                ms.march_moves_remaining -= 1
            else:
                # Defensive: if a stand-alone move is dispatched (e.g. via a
                # bird-card-granted action), it consumes a full action.
                ms.actions_remaining -= 1

    def _handle_battle(self, state: GameState, action: Action) -> None:
        defender = Faction[action.payload["defender"]]
        clearing_id = int(action.payload["clearing"])
        result = resolve_battle(
            state,
            attacker=action.actor,
            defender=defender,
            clearing_id=clearing_id,
            rng=self._rng,
            use_ambush=bool(action.payload.get("ambush", False)),
        )
        state.append_log(
            f"Battle in {clearing_id}: {action.actor.name} vs {defender.name} "
            f"(+{result.attacker_vp}/{result.defender_vp} VP)"
        )
        if action.actor == Faction.MARQUISE:
            ms = state.players[Faction.MARQUISE]
            assert isinstance(ms, MarquiseState)
            ms.actions_remaining -= 1
        # Vagabond hostile relationship (9.2.9.III)
        if (
            action.actor == Faction.VAGABOND
            and result.defender_warriors_lost > 0
            and defender != Faction.VAGABOND
        ):
            v = state.players[Faction.VAGABOND]
            assert isinstance(v, VagabondState)
            v.relationships[defender] = VagabondRelationship.HOSTILE

    def _handle_craft(self, state: GameState, action: Action) -> None:
        faction = action.actor
        card_id = int(action.payload["card"])
        ps = state.players[faction]
        card = next((c for c in ps.hand if c.card_id == card_id), None)
        if card is None:
            raise ValueError("Card not in hand.")
        if not self._has_crafting_for(state, faction, card.cost.suits):
            raise ValueError("Crafting cost not satisfied.")
        ps.hand.remove(card)
        if card.effect.kind == CraftEffectType.ITEM and card.effect.item is not None:
            ps.crafted_items.append(card.effect.item)
            points = card.effect.points
            if faction == Faction.EYRIE:
                points = 1  # Disdain for Trade (7.2.3)
            ps.victory_points += points
            state.discard(card)
        elif card.effect.kind == CraftEffectType.PERSISTENT and card.effect.persistent_id:
            if card.effect.persistent_id in ps.persistent_effects:
                raise ValueError("Persistent effect already crafted (4.1.4).")
            ps.persistent_effects.add(card.effect.persistent_id)
        else:
            state.discard(card)

    def _has_crafting_for(
        self,
        state: GameState,
        faction: Faction,
        cost: Sequence[Suit],
    ) -> bool:
        if not cost:
            return True
        suits_needed: list[Suit] = list(cost)
        available = self._crafting_suits_available(state, faction)
        for required in suits_needed:
            if required in available:
                available.remove(required)
            elif Suit.BIRD in available and required != Suit.BIRD:
                available.remove(Suit.BIRD)
            else:
                return False
        return True

    def _crafting_suits_available(self, state: GameState, faction: Faction) -> list[Suit]:
        suits: list[Suit] = []
        for clearing in state.board.clearings.values():
            if faction == Faction.MARQUISE and clearing.has_building(
                BuildingType.WORKSHOP, Faction.MARQUISE
            ):
                suits.append(clearing.suit)
            if faction == Faction.EYRIE and clearing.has_building(
                BuildingType.ROOST, Faction.EYRIE
            ):
                suits.append(clearing.suit)
            if faction == Faction.ALLIANCE and clearing.has_token(
                Faction.ALLIANCE, TokenType.SYMPATHY
            ):
                suits.append(clearing.suit)
        if faction == Faction.VAGABOND:
            v = state.players[Faction.VAGABOND]
            assert isinstance(v, VagabondState)
            if v.pawn_clearing is not None:
                clearing = state.board.clearings[v.pawn_clearing]
                hammers = sum(
                    1 for it in v.satchel + v.hammer_track
                    if it.item == ItemType.HAMMER
                    and it.state in (ItemState.SATCHEL_FACE_UP, ItemState.TRACK_FACE_UP)
                )
                suits.extend([clearing.suit] * hammers)
        return suits

    def _craft_actions(self, state: GameState, faction: Faction) -> list[Action]:
        ps = state.players[faction]
        actions: list[Action] = []
        for card in ps.hand:
            if card.kind != CardKind.STANDARD:
                continue
            if self._has_crafting_for(state, faction, card.cost.suits):
                actions.append(Action(faction, A_CRAFT, {"card": card.card_id}))
        return actions

    def _dominance_actions(self, state: GameState, faction: Faction) -> list[Action]:
        ps = state.players[faction]
        if faction == Faction.VAGABOND:
            return []
        if ps.has_activated_dominance or ps.victory_points < 10:
            return []
        actions = []
        for card in ps.hand:
            if card.kind == CardKind.DOMINANCE:
                actions.append(
                    Action(faction, A_ACTIVATE_DOMINANCE, {"card": card.card_id})
                )
        return actions

    def _handle_activate_dominance(self, state: GameState, action: Action) -> None:
        ps = state.players[action.actor]
        card_id = int(action.payload["card"])
        card = next((c for c in ps.hand if c.card_id == card_id), None)
        if card is None or card.kind != CardKind.DOMINANCE:
            raise ValueError("Dominance card not in hand.")
        ps.hand.remove(card)
        ps.dominance_card = card
        ps.has_activated_dominance = True

    # Marquise -----------------------------------------------------------
    def _handle_marquise_build(self, state: GameState, action: Action) -> None:
        ms = state.players[Faction.MARQUISE]
        assert isinstance(ms, MarquiseState)
        cid = int(action.payload["clearing"])
        building = BuildingType[action.payload["building"]]
        clearing = state.board.clearings[cid]
        if clearing.ruling_faction(eyrie_lords_of_forest=True) != Faction.MARQUISE:
            raise ValueError("Build target must be ruled.")
        if clearing.open_slots() <= 0:
            raise ValueError("No open slots.")
        cost = self._marquise_building_cost(ms, building)
        if not self._spend_marquise_wood(state, cid, cost):
            raise ValueError("Not enough connected wood to pay cost.")
        clearing.place_building(Faction.MARQUISE, building)
        if building == BuildingType.SAWMILL:
            ms.sawmills_remaining -= 1
            ms.victory_points += self._next_track_points(ms, BuildingType.SAWMILL)
        elif building == BuildingType.WORKSHOP:
            ms.workshops_remaining -= 1
            ms.victory_points += self._next_track_points(ms, BuildingType.WORKSHOP)
        elif building == BuildingType.RECRUITER:
            ms.recruiters_remaining -= 1
            ms.victory_points += self._next_track_points(ms, BuildingType.RECRUITER)
        ms.actions_remaining -= 1

    def _marquise_building_cost(self, ms: MarquiseState, building: BuildingType) -> int:
        # Track costs from the Marquise faction board (left to right).
        track_remaining = {
            BuildingType.SAWMILL: ms.sawmills_remaining,
            BuildingType.WORKSHOP: ms.workshops_remaining,
            BuildingType.RECRUITER: ms.recruiters_remaining,
        }[building]
        # 6 buildings per type; cost columns: 0,1,2,3,4 wood (0 for first, etc.)
        placed = 6 - track_remaining
        cost_table = [0, 1, 2, 3, 4]
        return cost_table[min(placed, len(cost_table) - 1)]

    def _next_track_points(self, ms: MarquiseState, building: BuildingType) -> int:
        # Building VP rewards: 0,1,2,3,4,5
        track_remaining = {
            BuildingType.SAWMILL: ms.sawmills_remaining,
            BuildingType.WORKSHOP: ms.workshops_remaining,
            BuildingType.RECRUITER: ms.recruiters_remaining,
        }[building]
        placed = 6 - track_remaining
        rewards = [0, 1, 2, 3, 4, 5]
        return rewards[min(placed, len(rewards) - 1)]

    def _spend_marquise_wood(self, state: GameState, clearing_id: int, cost: int) -> bool:
        if cost <= 0:
            return True
        # Allow wood from the chosen clearing or connected clearings ruled by Marquise
        candidates = self._connected_marquise_wood(state, clearing_id)
        total = sum(c["wood"] for c in candidates)
        if total < cost:
            return False
        remaining = cost
        for entry in candidates:
            while entry["wood"] > 0 and remaining > 0:
                state.board.clearings[entry["cid"]].remove_token(
                    Faction.MARQUISE, TokenType.WOOD
                )
                entry["wood"] -= 1
                remaining -= 1
            if remaining == 0:
                break
        return True

    def _connected_marquise_wood(
        self,
        state: GameState,
        start: int,
    ) -> list[dict]:
        seen: set[int] = set()
        frontier = [start]
        result: list[dict] = []
        while frontier:
            cid = frontier.pop()
            if cid in seen:
                continue
            seen.add(cid)
            clearing = state.board.clearings[cid]
            if clearing.ruling_faction(eyrie_lords_of_forest=True) != Faction.MARQUISE and cid != start:
                continue
            wood = sum(
                1
                for owner, kind in clearing.tokens
                if owner == Faction.MARQUISE and kind == TokenType.WOOD
            )
            if wood:
                result.append({"cid": cid, "wood": wood})
            for adj in state.board.adjacent_clearings(cid):
                if adj not in seen:
                    frontier.append(adj)
        return result

    def _handle_marquise_march(self, state: GameState, action: Action) -> None:
        ms = state.players[Faction.MARQUISE]
        assert isinstance(ms, MarquiseState)
        if ms.actions_remaining <= 0:
            raise ValueError("No actions remaining for March (Law 6.5).")
        if ms.march_moves_remaining > 0:
            raise ValueError("A march is already in progress.")
        ms.actions_remaining -= 1
        ms.march_moves_remaining = 2

    def _handle_marquise_end_march(self, state: GameState, action: Action) -> None:
        ms = state.players[Faction.MARQUISE]
        assert isinstance(ms, MarquiseState)
        if ms.march_moves_remaining <= 0:
            raise ValueError("No active march to end.")
        ms.march_moves_remaining = 0

    def _handle_marquise_recruit(self, state: GameState, action: Action) -> None:
        ms = state.players[Faction.MARQUISE]
        assert isinstance(ms, MarquiseState)
        if ms.recruit_used_this_turn:
            raise ValueError("Recruit already used this turn (Law 6.5.3).")
        for clearing in state.board.clearings.values():
            recruiters = sum(
                1 for owner, kind in clearing.buildings
                if owner == Faction.MARQUISE and kind == BuildingType.RECRUITER
            )
            for _ in range(recruiters):
                if ms.warriors_in_supply <= 0:
                    break
                clearing.add_warriors(Faction.MARQUISE, 1)
                ms.warriors_in_supply -= 1
        ms.recruit_used_this_turn = True
        ms.actions_remaining -= 1

    def _handle_marquise_overwork(self, state: GameState, action: Action) -> None:
        ms = state.players[Faction.MARQUISE]
        assert isinstance(ms, MarquiseState)
        cid = int(action.payload["clearing"])
        card_id = int(action.payload["card"])
        card = next((c for c in ms.hand if c.card_id == card_id), None)
        clearing = state.board.clearings[cid]
        if card is None or not clearing.has_building(BuildingType.SAWMILL, Faction.MARQUISE):
            raise ValueError("Invalid Overwork.")
        if card.suit != clearing.suit and card.suit != Suit.BIRD:
            raise ValueError("Card suit must match clearing or be a bird (Law 6.5.5).")
        ms.hand.remove(card)
        state.discard(card)
        if ms.wood_in_supply > 0:
            clearing.place_token(Faction.MARQUISE, TokenType.WOOD)
            ms.wood_in_supply -= 1
        ms.actions_remaining -= 1

    def _handle_marquise_spend_bird(self, state: GameState, action: Action) -> None:
        ms = state.players[Faction.MARQUISE]
        assert isinstance(ms, MarquiseState)
        card_id = int(action.payload["card"])
        card = next((c for c in ms.hand if c.card_id == card_id), None)
        if card is None or card.suit != Suit.BIRD:
            raise ValueError("Must spend a bird card (Law 6.5).")
        ms.hand.remove(card)
        state.discard(card)
        ms.actions_remaining += 1

    # Eyrie --------------------------------------------------------------
    def _handle_eyrie_add_to_decree(self, state: GameState, action: Action) -> None:
        es = state.players[Faction.EYRIE]
        assert isinstance(es, EyrieState)
        col = DecreeColumn[action.payload["column"]]
        card_id = int(action.payload["card"])
        card = next((c for c in es.hand if c.card_id == card_id), None)
        if card is None:
            raise ValueError("Card not in hand.")
        # Only one bird per Birdsong addition (7.4.2). Simplified: don't track,
        # rely on player to comply per Law 1.1.3.
        es.hand.remove(card)
        es.decree[col].append(card)

    def _handle_eyrie_resolve_decree_card(self, state: GameState, action: Action) -> None:
        es = state.players[Faction.EYRIE]
        assert isinstance(es, EyrieState)
        col = DecreeColumn[action.payload["column"]]
        if not es.decree[col]:
            raise ValueError("No decree cards in column.")
        # Pop the first card and resolve a small action of its column type.
        card = es.decree[col].pop(0)
        # Simplified resolutions
        try:
            if col == DecreeColumn.RECRUIT:
                self._eyrie_recruit_for(state, card.suit)
            elif col == DecreeColumn.MOVE:
                self._eyrie_auto_move(state, card.suit)
            elif col == DecreeColumn.BATTLE:
                self._eyrie_auto_battle(state, card.suit)
            elif col == DecreeColumn.BUILD:
                self._eyrie_auto_build(state, card.suit)
        except ValueError:
            self._eyrie_turmoil(state)
            return
        if card is not _LOYAL_VIZIER:
            state.discard(card)
        else:
            es.decree[col].append(_LOYAL_VIZIER)

    def _eyrie_recruit_for(self, state: GameState, suit: Suit) -> None:
        es = state.players[Faction.EYRIE]
        assert isinstance(es, EyrieState)
        for clearing in state.board.clearings.values():
            if clearing.has_building(BuildingType.ROOST, Faction.EYRIE):
                if suit in (clearing.suit, Suit.BIRD) and es.warriors_in_supply > 0:
                    clearing.add_warriors(Faction.EYRIE, 1)
                    es.warriors_in_supply -= 1
                    return
        raise ValueError("Cannot recruit (no matching roost).")

    def _eyrie_auto_move(self, state: GameState, suit: Suit) -> None:
        for clearing in state.board.clearings.values():
            if (
                clearing.warriors.get(Faction.EYRIE, 0) > 0
                and (clearing.suit == suit or suit == Suit.BIRD)
            ):
                for adj in state.board.adjacent_clearings(clearing.clearing_id):
                    if (
                        clearing.ruling_faction(eyrie_lords_of_forest=True) == Faction.EYRIE
                        or state.board.clearings[adj].ruling_faction(eyrie_lords_of_forest=True)
                        == Faction.EYRIE
                    ):
                        clearing.remove_warriors(Faction.EYRIE, 1)
                        state.board.clearings[adj].add_warriors(Faction.EYRIE, 1)
                        return
        raise ValueError("Cannot move from a matching clearing.")

    def _eyrie_auto_battle(self, state: GameState, suit: Suit) -> None:
        for clearing in state.board.clearings.values():
            if (
                clearing.warriors.get(Faction.EYRIE, 0) > 0
                and (clearing.suit == suit or suit == Suit.BIRD)
            ):
                enemies = [
                    f for f in clearing.warriors
                    if f != Faction.EYRIE and clearing.warriors[f] > 0
                ]
                if not enemies and not clearing.has_vagabond:
                    continue
                target = enemies[0] if enemies else Faction.VAGABOND
                resolve_battle(
                    state,
                    attacker=Faction.EYRIE,
                    defender=target,
                    clearing_id=clearing.clearing_id,
                    rng=self._rng,
                )
                return
        raise ValueError("Cannot battle in a matching clearing.")

    def _eyrie_auto_build(self, state: GameState, suit: Suit) -> None:
        es = state.players[Faction.EYRIE]
        assert isinstance(es, EyrieState)
        if es.roosts_remaining <= 0:
            raise ValueError("No roosts left to build.")
        for clearing in state.board.clearings.values():
            if (
                clearing.ruling_faction(eyrie_lords_of_forest=True) == Faction.EYRIE
                and (clearing.suit == suit or suit == Suit.BIRD)
                and clearing.open_slots() > 0
                and not clearing.has_building(BuildingType.ROOST, Faction.EYRIE)
            ):
                clearing.place_building(Faction.EYRIE, BuildingType.ROOST)
                es.roosts_remaining -= 1
                return
        raise ValueError("Cannot build a roost in a matching ruled clearing.")

    def _eyrie_turmoil(self, state: GameState) -> None:
        es = state.players[Faction.EYRIE]
        assert isinstance(es, EyrieState)
        # 7.7.1 Humiliate
        bird_count = sum(
            1 for col in es.decree.values() for c in col
            if c is _LOYAL_VIZIER or c.suit == Suit.BIRD
        )
        es.victory_points = max(0, es.victory_points - bird_count)
        # 7.7.2 Purge
        for col in DecreeColumn:
            es.decree[col] = [c for c in es.decree[col] if c is _LOYAL_VIZIER]
        # 7.7.3 Depose
        if es.leader is not None:
            es.used_leaders.append(es.leader)
            es.leader = None
        if not es.available_leaders:
            es.available_leaders = list(es.used_leaders)
            es.used_leaders.clear()
        es.leader = es.available_leaders.pop(0)
        for col in DecreeColumn:
            es.decree[col] = [c for c in es.decree[col] if c is not _LOYAL_VIZIER]
        self._tuck_loyal_viziers(es, es.leader)
        # 7.7.4 Rest -> end Daylight, begin Evening
        if state.current_phase == Phase.DAYLIGHT:
            state.current_phase = Phase.EVENING

    def _handle_eyrie_build_roost(self, state: GameState, action: Action) -> None:
        es = state.players[Faction.EYRIE]
        assert isinstance(es, EyrieState)
        cid = int(action.payload["clearing"])
        clearing = state.board.clearings[cid]
        if clearing.ruling_faction(eyrie_lords_of_forest=True) != Faction.EYRIE:
            raise ValueError("Eyrie must rule the clearing to place a roost.")
        if clearing.has_building(BuildingType.ROOST, Faction.EYRIE):
            raise ValueError("Roost already present.")
        if es.roosts_remaining <= 0:
            raise ValueError("No roosts available.")
        clearing.place_building(Faction.EYRIE, BuildingType.ROOST)
        es.roosts_remaining -= 1

    # Alliance -----------------------------------------------------------
    def _handle_alliance_revolt(self, state: GameState, action: Action) -> None:
        a = state.players[Faction.ALLIANCE]
        assert isinstance(a, AllianceState)
        cid = int(action.payload["clearing"])
        clearing = state.board.clearings[cid]
        if not clearing.has_token(Faction.ALLIANCE, TokenType.SYMPATHY):
            raise ValueError("Clearing is not sympathetic.")
        suit_to_base = {
            Suit.FOX: BuildingType.BASE_FOX,
            Suit.RABBIT: BuildingType.BASE_RABBIT,
            Suit.MOUSE: BuildingType.BASE_MOUSE,
        }
        base = suit_to_base.get(clearing.suit)
        if base is None or a.bases_remaining.get(base, 0) <= 0:
            raise ValueError("No matching base available.")
        # Spend two supporters of clearing's suit (or birds)
        if not self._spend_supporters(a, clearing.suit, count=2):
            raise ValueError("Not enough matching supporters.")
        # Remove all enemy pieces in clearing, scoring per token/building
        for enemy in list(clearing.warriors.keys()):
            if enemy != Faction.ALLIANCE:
                clearing.warriors.pop(enemy, None)
        for owner, kind in list(clearing.buildings):
            if owner not in (None, Faction.ALLIANCE) and kind != BuildingType.RUIN:
                clearing.remove_building(kind, owner)
                a.victory_points += 1
        for owner, kind in list(clearing.tokens):
            if owner != Faction.ALLIANCE:
                clearing.remove_token(owner, kind)
                a.victory_points += 1
        # Place base and warriors equal to sympathetic clearings of base suit
        clearing.place_building(Faction.ALLIANCE, base)
        a.bases_remaining[base] -= 1
        a.bases_on_map.append(base)
        warriors_to_place = sum(
            1 for c in state.board.clearings.values()
            if c.suit == clearing.suit and c.has_token(Faction.ALLIANCE, TokenType.SYMPATHY)
        )
        warriors_to_place = min(warriors_to_place, a.warriors_in_supply)
        clearing.add_warriors(Faction.ALLIANCE, warriors_to_place)
        a.warriors_in_supply -= warriors_to_place
        if a.warriors_in_supply > 0:
            a.officers += 1
            a.warriors_in_supply -= 1

    def _handle_alliance_spread_sympathy(self, state: GameState, action: Action) -> None:
        a = state.players[Faction.ALLIANCE]
        assert isinstance(a, AllianceState)
        cid = int(action.payload["clearing"])
        clearing = state.board.clearings[cid]
        if clearing.has_token(Faction.ALLIANCE, TokenType.SYMPATHY):
            raise ValueError("Already sympathetic.")
        if a.sympathy_tokens_remaining <= 0:
            raise ValueError("No sympathy tokens left.")
        # Determine cost (1 base, +1 if 3+ enemy warriors, +1 per martial law)
        enemy_warriors = sum(
            n for f, n in clearing.warriors.items() if f != Faction.ALLIANCE
        )
        # Token row cost (10..7 cost 1, 6..4 cost 2, 3..1 cost 2 per Law 8.2.5 / setup)
        placed = 10 - a.sympathy_tokens_remaining
        cost = 1 if placed < 3 else 2
        if enemy_warriors >= 3:
            cost += 1
        if not self._spend_supporters(a, clearing.suit, count=cost):
            raise ValueError("Not enough matching supporters.")
        clearing.place_token(Faction.ALLIANCE, TokenType.SYMPATHY)
        a.sympathy_tokens_remaining -= 1
        # Score per uncovered space (simplified: 1 VP early, 2 VP later)
        a.victory_points += 1 if placed < 3 else 2

    def _handle_alliance_mobilize(self, state: GameState, action: Action) -> None:
        a = state.players[Faction.ALLIANCE]
        assert isinstance(a, AllianceState)
        card_id = int(action.payload["card"])
        card = next((c for c in a.hand if c.card_id == card_id), None)
        if card is None:
            raise ValueError("Card not in hand.")
        a.hand.remove(card)
        if not a.add_supporter(card):
            state.discard(card)

    def _handle_alliance_train(self, state: GameState, action: Action) -> None:
        a = state.players[Faction.ALLIANCE]
        assert isinstance(a, AllianceState)
        card_id = int(action.payload["card"])
        base = BuildingType[action.payload["base"]]
        if base not in a.bases_on_map:
            raise ValueError("Matching base must be on the map.")
        card = next((c for c in a.hand if c.card_id == card_id), None)
        if card is None:
            raise ValueError("Card not in hand.")
        a.hand.remove(card)
        state.discard(card)
        if a.warriors_in_supply > 0:
            a.officers += 1
            a.warriors_in_supply -= 1

    def _handle_alliance_mil_op(self, state: GameState, action: Action) -> None:
        a = state.players[Faction.ALLIANCE]
        assert isinstance(a, AllianceState)
        if a.officer_actions_remaining <= 0:
            raise ValueError("No officers remaining for actions.")
        kind = action.payload.get("action")
        if kind == "recruit":
            for clearing in state.board.clearings.values():
                if any(
                    owner == Faction.ALLIANCE and bk in {
                        BuildingType.BASE_FOX,
                        BuildingType.BASE_RABBIT,
                        BuildingType.BASE_MOUSE,
                    }
                    for owner, bk in clearing.buildings
                ):
                    if a.warriors_in_supply > 0:
                        clearing.add_warriors(Faction.ALLIANCE, 1)
                        a.warriors_in_supply -= 1
        elif kind == "organize":
            for clearing in state.board.clearings.values():
                if (
                    clearing.warriors.get(Faction.ALLIANCE, 0) > 0
                    and not clearing.has_token(Faction.ALLIANCE, TokenType.SYMPATHY)
                    and a.sympathy_tokens_remaining > 0
                ):
                    clearing.remove_warriors(Faction.ALLIANCE, 1)
                    a.warriors_in_supply += 1
                    clearing.place_token(Faction.ALLIANCE, TokenType.SYMPATHY)
                    a.sympathy_tokens_remaining -= 1
                    a.victory_points += 1
                    break
        a.officer_actions_remaining -= 1

    def _spend_supporters(self, a: AllianceState, suit: Suit, count: int) -> bool:
        chosen: list[Card] = []
        # Spend matching suit first, then birds
        for card in list(a.supporters):
            if len(chosen) >= count:
                break
            if card.suit == suit:
                chosen.append(card)
        for card in list(a.supporters):
            if len(chosen) >= count:
                break
            if card.suit == Suit.BIRD and card not in chosen:
                chosen.append(card)
        if len(chosen) < count:
            return False
        for card in chosen:
            a.supporters.remove(card)
        return True

    # Vagabond -----------------------------------------------------------
    def _handle_vagabond_slip(self, state: GameState, action: Action) -> None:
        v = state.players[Faction.VAGABOND]
        assert isinstance(v, VagabondState)
        if "from_clearing" in action.payload:
            state.board.clearings[int(action.payload["from_clearing"])].has_vagabond = False
        if "to_clearing" in action.payload:
            cid = int(action.payload["to_clearing"])
            v.pawn_clearing = cid
            v.pawn_forest = None
            state.board.clearings[cid].has_vagabond = True
        elif "to_forest" in action.payload:
            v.pawn_clearing = None
            v.pawn_forest = action.payload["to_forest"]

    def _handle_vagabond_explore(self, state: GameState, action: Action) -> None:
        v = state.players[Faction.VAGABOND]
        assert isinstance(v, VagabondState)
        cid = int(action.payload["clearing"])
        clearing = state.board.clearings[cid]
        if not any(kind == BuildingType.RUIN for _, kind in clearing.buildings):
            raise ValueError("No ruin in clearing.")
        if not self._vagabond_exhaust_item(v, ItemType.TORCH):
            raise ValueError("Need an undamaged torch.")
        clearing.remove_building(BuildingType.RUIN, None)
        # Reward: gain a random ruin item
        v.add_item(ItemType.HAMMER)
        v.victory_points += 1

    def _handle_vagabond_aid(self, state: GameState, action: Action) -> None:
        v = state.players[Faction.VAGABOND]
        assert isinstance(v, VagabondState)
        target = Faction[action.payload["faction"]]
        card_id = int(action.payload["card"])
        card = next((c for c in v.hand if c.card_id == card_id), None)
        if card is None:
            raise ValueError("Card not in hand.")
        if not self._vagabond_exhaust_item(v, None):
            raise ValueError("Need any undamaged item to aid.")
        v.hand.remove(card)
        state.players[target].hand.append(card)
        # Improve relationship (very simplified)
        rel = v.relationships.get(target, VagabondRelationship.INDIFFERENT)
        order = list(VagabondRelationship)
        v.aids_given_this_turn[target] = v.aids_given_this_turn.get(target, 0) + 1
        if rel != VagabondRelationship.HOSTILE and v.aids_given_this_turn[target] >= 2:
            idx = order.index(rel)
            if idx < len(order) - 1:
                v.relationships[target] = order[idx + 1]
                v.victory_points += 1

    def _handle_vagabond_quest(self, state: GameState, action: Action) -> None:
        v = state.players[Faction.VAGABOND]
        assert isinstance(v, VagabondState)
        # Highly simplified: exhaust a hammer and a sword for one VP.
        if not self._vagabond_exhaust_item(v, ItemType.HAMMER):
            raise ValueError("Need a hammer for quest.")
        if not self._vagabond_exhaust_item(v, ItemType.SWORD):
            raise ValueError("Need a sword for quest.")
        v.completed_quests.append("Quest")
        v.victory_points += 1

    def _handle_vagabond_strike(self, state: GameState, action: Action) -> None:
        v = state.players[Faction.VAGABOND]
        assert isinstance(v, VagabondState)
        target = Faction[action.payload["defender"]]
        cid = int(action.payload["clearing"])
        if not self._vagabond_exhaust_item(v, ItemType.CROSSBOW):
            raise ValueError("Need a crossbow.")
        clearing = state.board.clearings[cid]
        if clearing.warriors.get(target, 0) > 0:
            clearing.remove_warriors(target, 1)
        elif clearing.tokens or clearing.buildings:
            removed = False
            for owner, kind in list(clearing.buildings):
                if owner == target and kind != BuildingType.RUIN:
                    clearing.remove_building(kind, owner)
                    v.victory_points += 1
                    removed = True
                    break
            if not removed:
                for owner, token in list(clearing.tokens):
                    if owner == target:
                        clearing.remove_token(owner, token)
                        v.victory_points += 1
                        break
        # Becoming hostile (9.2.9.III)
        v.relationships[target] = VagabondRelationship.HOSTILE

    def _handle_vagabond_repair(self, state: GameState, action: Action) -> None:
        v = state.players[Faction.VAGABOND]
        assert isinstance(v, VagabondState)
        if not v.damaged:
            raise ValueError("No damaged items.")
        if not self._vagabond_exhaust_item(v, ItemType.HAMMER):
            raise ValueError("Need a hammer.")
        item = v.damaged.pop(0)
        # Move it back to satchel/track in current face state
        v.add_item(item.item)

    def _handle_vagabond_special(self, state: GameState, action: Action) -> None:
        v = state.players[Faction.VAGABOND]
        assert isinstance(v, VagabondState)
        # Character-specific special action stubbed: Thief steals a card,
        # Tinker pulls from discard, Ranger refreshes one.
        if v.character == VagabondCharacter.THIEF:
            for f, ps in state.players.items():
                if f != Faction.VAGABOND and ps.hand:
                    card = ps.hand.pop()
                    v.hand.append(card)
                    return
        elif v.character == VagabondCharacter.TINKER:
            if state.discard_pile:
                v.hand.append(state.discard_pile.pop())
        elif v.character == VagabondCharacter.RANGER:
            self._refresh_three_items(v)

    def _refresh_three_items(self, v: VagabondState) -> None:
        from .factions import _refresh_items

        _refresh_items(v, 3)

    def _vagabond_exhaust_item(self, v: VagabondState, item: ItemType | None) -> bool:
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
        for pool in pools:
            for it in pool:
                if item is not None and it.item != item:
                    continue
                if it.state == ItemState.SATCHEL_FACE_UP:
                    it.state = ItemState.SATCHEL_FACE_DOWN
                    return True
                if it.state == ItemState.TRACK_FACE_UP:
                    it.state = ItemState.TRACK_FACE_DOWN
                    return True
        return False

    # Victory ------------------------------------------------------------
    def _check_victory(self, state: GameState) -> None:
        if state.winner is not None:
            return
        for faction, player in state.players.items():
            if faction == Faction.VAGABOND:
                continue
            if player.victory_points >= VICTORY_THRESHOLD:
                state.winner = faction
                return
        # Vagabond can win at 30 VP outside coalition (or with coalition partner)
        v = state.players.get(Faction.VAGABOND)
        if v and v.victory_points >= VICTORY_THRESHOLD:
            state.winner = Faction.VAGABOND
        # Dominance victory (3.3.1) at start of Birdsong - simplified to immediate
        for faction, player in state.players.items():
            if not player.has_activated_dominance or not player.dominance_card:
                continue
            card = player.dominance_card
            if card.suit in (Suit.FOX, Suit.RABBIT, Suit.MOUSE):
                ruled = sum(
                    1 for clearing in state.board.clearings.values()
                    if clearing.suit == card.suit
                    and clearing.ruling_faction(eyrie_lords_of_forest=True) == faction
                )
                if ruled >= 3 and state.current_phase == Phase.BIRDSONG:
                    state.winner = faction
                    return
            elif card.suit == Suit.BIRD:
                ruled_corners = [
                    cid for cid in CORNER_CLEARINGS
                    if state.board.clearings[cid].ruling_faction(eyrie_lords_of_forest=True) == faction
                ]
                if (
                    state.current_phase == Phase.BIRDSONG
                    and any(OPPOSITE_CORNERS.get(cid) in ruled_corners for cid in ruled_corners)
                ):
                    state.winner = faction
                    return


# Dispatch table ---------------------------------------------------------

_DISPATCH = {
    A_END_PHASE: RulesEngine._handle_end_phase,
    A_MOVE: RulesEngine._handle_move,
    A_BATTLE: RulesEngine._handle_battle,
    A_CRAFT: RulesEngine._handle_craft,
    A_ACTIVATE_DOMINANCE: RulesEngine._handle_activate_dominance,
    A_MARQUISE_BUILD: RulesEngine._handle_marquise_build,
    A_MARQUISE_RECRUIT: RulesEngine._handle_marquise_recruit,
    A_MARQUISE_OVERWORK: RulesEngine._handle_marquise_overwork,
    A_MARQUISE_SPEND_BIRD: RulesEngine._handle_marquise_spend_bird,
    A_MARQUISE_MARCH: RulesEngine._handle_marquise_march,
    A_MARQUISE_END_MARCH: RulesEngine._handle_marquise_end_march,
    A_EYRIE_ADD_TO_DECREE: RulesEngine._handle_eyrie_add_to_decree,
    A_EYRIE_RESOLVE_DECREE_CARD: RulesEngine._handle_eyrie_resolve_decree_card,
    A_EYRIE_BUILD_ROOST: RulesEngine._handle_eyrie_build_roost,
    A_ALLIANCE_REVOLT: RulesEngine._handle_alliance_revolt,
    A_ALLIANCE_SPREAD_SYMPATHY: RulesEngine._handle_alliance_spread_sympathy,
    A_ALLIANCE_MOBILIZE: RulesEngine._handle_alliance_mobilize,
    A_ALLIANCE_TRAIN: RulesEngine._handle_alliance_train,
    A_ALLIANCE_MIL_OP: RulesEngine._handle_alliance_mil_op,
    A_VAGABOND_SLIP: RulesEngine._handle_vagabond_slip,
    A_VAGABOND_EXPLORE: RulesEngine._handle_vagabond_explore,
    A_VAGABOND_AID: RulesEngine._handle_vagabond_aid,
    A_VAGABOND_QUEST: RulesEngine._handle_vagabond_quest,
    A_VAGABOND_STRIKE: RulesEngine._handle_vagabond_strike,
    A_VAGABOND_REPAIR: RulesEngine._handle_vagabond_repair,
    A_VAGABOND_SPECIAL: RulesEngine._handle_vagabond_special,
}


# Loyal Vizier sentinel ---------------------------------------------------

_LOYAL_VIZIER = Card(
    card_id=-1,
    name="Loyal Vizier",
    suit=Suit.BIRD,
    kind=CardKind.STANDARD,
)
