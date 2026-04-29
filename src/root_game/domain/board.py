"""Board / autumn map implementation for Root base game.

The autumn map has 12 clearings (4 each of fox, rabbit, mouse), 4 corner
clearings, and 4 ruins. Suits and slots below match the standard fall map
shipped with the base game (best-effort representation suitable for a
text-based engine).

Per the Law:
- 2.2.1 Adjacency: clearings are adjacent if linked by a path.
- 2.2.3 Slots: each clearing has building slots; ruins fill some at start.
- 2.4 Forests are areas enclosed by paths and clearings.
- 2.5 Rule: more total warriors+buildings than each other player.
"""

from dataclasses import dataclass, field

from .enums import (
    BuildingType,
    Faction,
    Suit,
    TokenType,
)


@dataclass
class Clearing:
    clearing_id: int
    suit: Suit
    slots: int
    is_corner: bool = False
    on_river: bool = False
    warriors: dict[Faction, int] = field(default_factory=dict)
    buildings: list[tuple[Faction | None, BuildingType]] = field(default_factory=list)
    tokens: list[tuple[Faction, TokenType]] = field(default_factory=list)
    has_vagabond: bool = False

    # Crafting helpers ----------------------------------------------------
    def has_building(self, building: BuildingType, faction: Faction | None = None) -> bool:
        for owner, kind in self.buildings:
            if kind != building:
                continue
            if faction is None or owner == faction:
                return True
        return False

    def building_count(self, faction: Faction) -> int:
        return sum(1 for owner, _ in self.buildings if owner == faction)

    def token_count(self, faction: Faction) -> int:
        return sum(1 for owner, _ in self.tokens if owner == faction)

    def open_slots(self) -> int:
        return self.slots - len(self.buildings)

    # Pieces --------------------------------------------------------------
    def add_warriors(self, faction: Faction, amount: int = 1) -> None:
        if amount <= 0:
            return
        self.warriors[faction] = self.warriors.get(faction, 0) + amount

    def remove_warriors(self, faction: Faction, amount: int = 1) -> None:
        current = self.warriors.get(faction, 0)
        if amount > current:
            raise ValueError(
                f"Cannot remove {amount} warriors of {faction.name} from clearing "
                f"{self.clearing_id} (only {current})."
            )
        new_count = current - amount
        if new_count == 0:
            self.warriors.pop(faction, None)
        else:
            self.warriors[faction] = new_count

    def place_building(self, faction: Faction | None, building: BuildingType) -> None:
        if self.open_slots() <= 0:
            raise ValueError(f"No open slots in clearing {self.clearing_id}.")
        self.buildings.append((faction, building))

    def remove_building(self, building: BuildingType, faction: Faction | None = None) -> None:
        for idx, (owner, kind) in enumerate(self.buildings):
            if kind != building:
                continue
            if faction is not None and owner != faction:
                continue
            self.buildings.pop(idx)
            return
        raise ValueError(
            f"No matching building {building.name} in clearing {self.clearing_id}."
        )

    def place_token(self, faction: Faction, token: TokenType) -> None:
        self.tokens.append((faction, token))

    def remove_token(self, faction: Faction, token: TokenType) -> None:
        for idx, (owner, kind) in enumerate(self.tokens):
            if owner == faction and kind == token:
                self.tokens.pop(idx)
                return
        raise ValueError(
            f"No {faction.name} {token.name} token in clearing {self.clearing_id}."
        )

    def has_token(self, faction: Faction, token: TokenType) -> bool:
        return any(o == faction and t == token for o, t in self.tokens)

    # Rule ---------------------------------------------------------------
    def faction_strength(self, faction: Faction) -> int:
        return self.warriors.get(faction, 0) + self.building_count(faction)

    def ruling_faction(self, eyrie_lords_of_forest: bool = False) -> Faction | None:
        """Return the ruling faction per Law 2.5; None on tie or empty.

        If `eyrie_lords_of_forest` is True, Eyrie wins ties on which they have
        any piece (Law 7.2.2 Lords of the Forest).
        """
        strengths = {f: self.faction_strength(f) for f in Faction}
        max_strength = max(strengths.values())
        if max_strength == 0:
            return None
        leaders = [f for f, s in strengths.items() if s == max_strength]
        if len(leaders) == 1:
            return leaders[0]
        if eyrie_lords_of_forest and Faction.EYRIE in leaders:
            eyrie_pieces = (
                self.warriors.get(Faction.EYRIE, 0)
                + self.building_count(Faction.EYRIE)
                + self.token_count(Faction.EYRIE)
            )
            if eyrie_pieces > 0:
                return Faction.EYRIE
        return None


@dataclass
class Board:
    clearings: dict[int, Clearing]
    paths: set[tuple[int, int]]
    forests: dict[str, set[int]]

    @classmethod
    def autumn_map(cls) -> "Board":
        """Standard fall map.

        Layout (corner indices 1, 5, 9, 12). Suits and slot counts approximate
        the printed fall map; ruin clearings are 6, 7, 10, 11 (each has a
        ruin filling one slot per Law 2.2.4, leaving the other slot open).
        Every clearing has at least 2 slots so the Marquise's setup
        (Law 6.3.4) can always place 3 starting buildings in keep+adjacent.
        """
        clearing_specs: list[tuple[int, Suit, int, bool, bool]] = [
            (1, Suit.FOX, 2, True, False),
            (2, Suit.RABBIT, 3, False, False),
            (3, Suit.RABBIT, 2, False, True),
            (4, Suit.MOUSE, 2, False, True),
            (5, Suit.MOUSE, 2, True, False),
            (6, Suit.RABBIT, 2, False, False),
            (7, Suit.FOX, 2, False, False),
            (8, Suit.MOUSE, 3, False, False),
            (9, Suit.FOX, 2, True, False),
            (10, Suit.MOUSE, 2, False, False),
            (11, Suit.RABBIT, 2, False, False),
            (12, Suit.FOX, 2, True, False),
        ]
        clearings: dict[int, Clearing] = {}
        for cid, suit, slots, is_corner, on_river in clearing_specs:
            clearings[cid] = Clearing(
                clearing_id=cid,
                suit=suit,
                slots=slots,
                is_corner=is_corner,
                on_river=on_river,
            )

        # Place ruins (4 ruins) - they fill a slot in their clearing.
        for ruin_id in (6, 7, 10, 11):
            clearings[ruin_id].place_building(None, BuildingType.RUIN)

        # Adjacency (representative of the autumn map's connectivity).
        path_pairs = [
            (1, 2), (1, 3), (1, 4),
            (2, 3), (2, 6),
            (3, 4), (3, 7),
            (4, 8),
            (5, 4), (5, 8),
            (6, 7), (6, 9),
            (7, 8), (7, 10), (7, 11),
            (8, 11),
            (9, 10),
            (10, 11),
            (11, 12),
            (10, 12),
        ]
        paths: set[tuple[int, int]] = {
            (a, b) if a < b else (b, a) for a, b in path_pairs
        }

        # Forests are areas enclosed by paths/clearings. We provide a
        # reasonable mapping of forest -> adjacent clearings for the
        # Vagabond's Slip and forest mechanics.
        forests: dict[str, set[int]] = {
            "F1": {1, 2, 3},
            "F2": {1, 3, 4},
            "F3": {2, 3, 6, 7},
            "F4": {3, 4, 7, 8},
            "F5": {4, 5, 8},
            "F6": {6, 7, 9, 10},
            "F7": {7, 8, 10, 11},
            "F8": {8, 11, 5},
            "F9": {10, 11, 12},
        }

        return cls(clearings=clearings, paths=paths, forests=forests)

    # Path queries --------------------------------------------------------
    def is_connected(self, a: int, b: int) -> bool:
        if a == b:
            return False
        edge = (a, b) if a < b else (b, a)
        return edge in self.paths

    def adjacent_clearings(self, clearing_id: int) -> list[int]:
        result: list[int] = []
        for a, b in self.paths:
            if a == clearing_id:
                result.append(b)
            elif b == clearing_id:
                result.append(a)
        return sorted(result)

    def forests_adjacent_to_clearing(self, clearing_id: int) -> list[str]:
        return sorted([fid for fid, members in self.forests.items() if clearing_id in members])

    def clearings_in_forest(self, forest_id: str) -> list[int]:
        return sorted(self.forests.get(forest_id, set()))

    def clearings_with_ruin(self) -> list[int]:
        result = []
        for cid, clearing in self.clearings.items():
            if any(kind == BuildingType.RUIN for _, kind in clearing.buildings):
                result.append(cid)
        return sorted(result)
