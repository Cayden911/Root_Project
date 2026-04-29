"""Enumerations for Root base game.

References from the Law of Root (Oct 13, 2025):
- 2.1 Cards / suits
- 2.2 Clearings
- 6 Marquise / 7 Eyrie / 8 Alliance / 9 Vagabond
- C.1 Components
"""

from enum import Enum, auto


class Faction(Enum):
    MARQUISE = auto()
    EYRIE = auto()
    ALLIANCE = auto()
    VAGABOND = auto()


class Suit(Enum):
    FOX = auto()
    RABBIT = auto()
    MOUSE = auto()
    BIRD = auto()


class Phase(Enum):
    BIRDSONG = auto()
    DAYLIGHT = auto()
    EVENING = auto()


class BuildingType(Enum):
    SAWMILL = auto()
    WORKSHOP = auto()
    RECRUITER = auto()
    ROOST = auto()
    BASE_FOX = auto()
    BASE_RABBIT = auto()
    BASE_MOUSE = auto()
    RUIN = auto()


class TokenType(Enum):
    KEEP = auto()
    WOOD = auto()
    SYMPATHY = auto()


class ItemType(Enum):
    BOOT = auto()
    SWORD = auto()
    BAG = auto()
    HAMMER = auto()
    TEA = auto()
    COIN = auto()
    CROSSBOW = auto()
    TORCH = auto()


class CardKind(Enum):
    STANDARD = auto()
    AMBUSH = auto()
    DOMINANCE = auto()


class CraftEffectType(Enum):
    ITEM = auto()
    PERSISTENT = auto()
    NONE = auto()


class EyrieLeader(Enum):
    BUILDER = auto()
    CHARISMATIC = auto()
    COMMANDER = auto()
    DESPOT = auto()


class DecreeColumn(Enum):
    RECRUIT = auto()
    MOVE = auto()
    BATTLE = auto()
    BUILD = auto()


class VagabondCharacter(Enum):
    THIEF = auto()
    TINKER = auto()
    RANGER = auto()


class VagabondRelationship(Enum):
    HOSTILE = auto()
    INDIFFERENT = auto()
    SYMPATHETIC = auto()
    FRIENDLY = auto()
    ALLIED = auto()


class ItemState(Enum):
    SATCHEL_FACE_UP = auto()
    SATCHEL_FACE_DOWN = auto()
    DAMAGED_FACE_UP = auto()
    DAMAGED_FACE_DOWN = auto()
    TRACK_FACE_UP = auto()
    TRACK_FACE_DOWN = auto()


CORNER_CLEARINGS: tuple[int, ...] = (1, 5, 9, 12)
"""Corner clearings on the standard autumn map (see map below)."""

OPPOSITE_CORNERS: dict[int, int] = {1: 12, 12: 1, 5: 9, 9: 5}
