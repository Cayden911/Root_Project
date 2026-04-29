"""Per-faction state structures.

These data classes hold all the bookkeeping needed by each base game
faction (Marquise, Eyrie, Alliance, Vagabond), per Law sections 6-9.
Where rule data is per-faction (decree, supporters stack, satchel) it
lives here; where it's global (deck, board) it lives on GameState.
"""

from dataclasses import dataclass, field

from .cards import Card
from .enums import (
    BuildingType,
    DecreeColumn,
    EyrieLeader,
    Faction,
    ItemState,
    ItemType,
    TokenType,
    VagabondCharacter,
    VagabondRelationship,
)


@dataclass
class FactionState:
    """Common state shared by all factions."""

    faction: Faction
    victory_points: int = 0
    hand: list[Card] = field(default_factory=list)
    crafted_items: list[ItemType] = field(default_factory=list)
    persistent_effects: set[str] = field(default_factory=set)
    eliminated: bool = False
    has_activated_dominance: bool = False
    dominance_card: Card | None = None
    coalition_partner: Faction | None = None


@dataclass
class MarquiseState(FactionState):
    """Marquise de Cat (Law 6).

    Tracks supplies of warriors/wood, building tracks, and per-turn flags.
    """

    warriors_in_supply: int = 25
    wood_in_supply: int = 8
    keep_placed: bool = False
    sawmills_remaining: int = 6
    workshops_remaining: int = 6
    recruiters_remaining: int = 6
    actions_remaining: int = 0
    march_moves_remaining: int = 0
    recruit_used_this_turn: bool = False
    crafting_used_workshops: set[int] = field(default_factory=set)
    starting_buildings_remaining: list[BuildingType] = field(
        default_factory=lambda: [
            BuildingType.SAWMILL,
            BuildingType.WORKSHOP,
            BuildingType.RECRUITER,
        ]
    )

    def __post_init__(self) -> None:
        self.faction = Faction.MARQUISE


@dataclass
class EyrieState(FactionState):
    """Eyrie Dynasties (Law 7)."""

    warriors_in_supply: int = 20
    roosts_remaining: int = 7
    leader: EyrieLeader | None = None
    available_leaders: list[EyrieLeader] = field(
        default_factory=lambda: list(EyrieLeader)
    )
    used_leaders: list[EyrieLeader] = field(default_factory=list)
    decree: dict[DecreeColumn, list[Card]] = field(
        default_factory=lambda: {col: [] for col in DecreeColumn}
    )
    decree_resolved_this_turn: dict[DecreeColumn, list[bool]] = field(default_factory=dict)
    crafting_used_roosts: set[int] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.faction = Faction.EYRIE


@dataclass
class AllianceState(FactionState):
    """Woodland Alliance (Law 8)."""

    warriors_in_supply: int = 10
    sympathy_tokens_remaining: int = 10
    bases_remaining: dict[BuildingType, int] = field(
        default_factory=lambda: {
            BuildingType.BASE_FOX: 1,
            BuildingType.BASE_RABBIT: 1,
            BuildingType.BASE_MOUSE: 1,
        }
    )
    bases_on_map: list[BuildingType] = field(default_factory=list)
    supporters: list[Card] = field(default_factory=list)
    officers: int = 0
    officer_actions_remaining: int = 0
    crafting_used_sympathy: set[int] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.faction = Faction.ALLIANCE

    def supporters_capacity(self) -> int:
        return 5 if not self.bases_on_map else 999

    def add_supporter(self, card: Card) -> bool:
        if len(self.supporters) >= self.supporters_capacity():
            return False
        self.supporters.append(card)
        return True


@dataclass
class VagabondItem:
    item: ItemType
    state: ItemState


@dataclass
class VagabondState(FactionState):
    """Vagabond (Law 9)."""

    character: VagabondCharacter | None = None
    pawn_clearing: int | None = None
    pawn_forest: str | None = None
    satchel: list[VagabondItem] = field(default_factory=list)
    damaged: list[VagabondItem] = field(default_factory=list)
    boots_track: list[VagabondItem] = field(default_factory=list)
    swords_track: list[VagabondItem] = field(default_factory=list)
    crossbow_track: list[VagabondItem] = field(default_factory=list)
    hammer_track: list[VagabondItem] = field(default_factory=list)
    teas_track: list[VagabondItem] = field(default_factory=list)
    coins_track: list[VagabondItem] = field(default_factory=list)
    bags_track: list[VagabondItem] = field(default_factory=list)
    relationships: dict[Faction, VagabondRelationship] = field(default_factory=dict)
    aids_given_this_turn: dict[Faction, int] = field(default_factory=dict)
    completed_quests: list[str] = field(default_factory=list)
    available_quests: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.faction = Faction.VAGABOND
        if not self.relationships:
            self.relationships = {
                f: VagabondRelationship.INDIFFERENT
                for f in (Faction.MARQUISE, Faction.EYRIE, Faction.ALLIANCE)
            }

    # Item management ----------------------------------------------------
    def all_items(self) -> list[VagabondItem]:
        return [
            *self.satchel,
            *self.damaged,
            *self.boots_track,
            *self.swords_track,
            *self.crossbow_track,
            *self.hammer_track,
            *self.teas_track,
            *self.coins_track,
            *self.bags_track,
        ]

    def item_capacity(self) -> int:
        return 6 + 2 * sum(
            1 for it in self.bags_track if it.state == ItemState.TRACK_FACE_UP
        )

    def undamaged_swords(self) -> int:
        return sum(
            1
            for it in self.satchel + self.swords_track
            if it.item == ItemType.SWORD
            and it.state in (ItemState.SATCHEL_FACE_UP, ItemState.TRACK_FACE_UP)
        )

    def add_item(self, item: ItemType) -> None:
        track_items = {ItemType.BOOT, ItemType.SWORD, ItemType.CROSSBOW,
                        ItemType.HAMMER, ItemType.TEA, ItemType.COIN, ItemType.BAG}
        if item in track_items:
            track = self._track_for(item)
            track.append(VagabondItem(item=item, state=ItemState.TRACK_FACE_UP))
        else:
            self.satchel.append(VagabondItem(item=item, state=ItemState.SATCHEL_FACE_UP))

    def _track_for(self, item: ItemType) -> list[VagabondItem]:
        if item == ItemType.BOOT:
            return self.boots_track
        if item == ItemType.SWORD:
            return self.swords_track
        if item == ItemType.CROSSBOW:
            return self.crossbow_track
        if item == ItemType.HAMMER:
            return self.hammer_track
        if item == ItemType.TEA:
            return self.teas_track
        if item == ItemType.COIN:
            return self.coins_track
        if item == ItemType.BAG:
            return self.bags_track
        return self.satchel
