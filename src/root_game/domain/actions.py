"""Action contract used by all UI/controller layers.

Actions are immutable command objects. The rules engine validates and
executes them. Payloads are plain dicts so this layer stays GUI-agnostic.
"""

from dataclasses import dataclass, field
from typing import Any

from .enums import Faction


@dataclass(frozen=True)
class Action:
    actor: Faction
    action_type: str
    payload: dict[str, Any] = field(default_factory=dict)

    def with_payload(self, **changes: Any) -> "Action":
        new_payload = dict(self.payload)
        new_payload.update(changes)
        return Action(actor=self.actor, action_type=self.action_type, payload=new_payload)


# Action type names used across the engine.
A_END_PHASE = "end_phase"

# Setup
A_SETUP_PLACE_KEEP = "setup_place_keep"
A_SETUP_PLACE_STARTING_BUILDING = "setup_place_starting_building"
A_SETUP_PLACE_ROOST = "setup_place_roost"
A_SETUP_CHOOSE_LEADER = "setup_choose_leader"
A_SETUP_PLACE_BASE_AND_OFFICERS = "setup_alliance_done"
A_SETUP_VAGABOND_PLACE = "setup_vagabond_place"
A_SETUP_VAGABOND_CHARACTER = "setup_vagabond_character"
A_SETUP_DONE = "setup_done"

# Generic shared actions
A_MOVE = "move"
A_BATTLE = "battle"
A_CRAFT = "craft"
A_DRAW = "draw"
A_DISCARD = "discard"
A_ACTIVATE_DOMINANCE = "activate_dominance"

# Marquise
A_MARQUISE_BUILD = "marquise_build"
A_MARQUISE_RECRUIT = "marquise_recruit"
A_MARQUISE_OVERWORK = "marquise_overwork"
A_MARQUISE_SPEND_BIRD = "marquise_spend_bird"
A_MARQUISE_MARCH = "marquise_march"
A_MARQUISE_END_MARCH = "marquise_end_march"

# Eyrie
A_EYRIE_ADD_TO_DECREE = "eyrie_add_to_decree"
A_EYRIE_RESOLVE_DECREE_CARD = "eyrie_resolve_decree_card"
A_EYRIE_BUILD_ROOST = "eyrie_build_roost"
A_EYRIE_TURMOIL = "eyrie_turmoil"

# Alliance
A_ALLIANCE_REVOLT = "alliance_revolt"
A_ALLIANCE_SPREAD_SYMPATHY = "alliance_spread_sympathy"
A_ALLIANCE_MOBILIZE = "alliance_mobilize"
A_ALLIANCE_TRAIN = "alliance_train"
A_ALLIANCE_MIL_OP = "alliance_military_operation"

# Vagabond
A_VAGABOND_SLIP = "vagabond_slip"
A_VAGABOND_EXPLORE = "vagabond_explore"
A_VAGABOND_AID = "vagabond_aid"
A_VAGABOND_QUEST = "vagabond_quest"
A_VAGABOND_STRIKE = "vagabond_strike"
A_VAGABOND_REPAIR = "vagabond_repair"
A_VAGABOND_SPECIAL = "vagabond_special"
