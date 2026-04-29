"""Top-level GameState for the Root base game."""

from dataclasses import dataclass, field
from typing import Iterable

from .board import Board
from .cards import Card, shuffled_deck
from .enums import (
    Faction,
    Phase,
)
from .faction_state import (
    AllianceState,
    EyrieState,
    FactionState,
    MarquiseState,
    VagabondState,
)


@dataclass
class GameState:
    """Game state for the Root base game.

    The state object is mutated in-place by the rules engine. It exposes
    helpers to query the current player, advance phases, and find the
    relevant faction-specific state record.
    """

    board: Board
    players: dict[Faction, FactionState]
    turn_order: list[Faction]
    deck: list[Card]
    discard_pile: list[Card] = field(default_factory=list)
    available_dominance: list[Card] = field(default_factory=list)
    current_turn_index: int = 0
    current_phase: Phase = Phase.BIRDSONG
    turn_count: int = 0
    setup_complete: bool = False
    setup_step: int = 0
    winner: Faction | None = None
    coalition_winner: Faction | None = None
    log: list[str] = field(default_factory=list)
    seat_count: int = 4

    @classmethod
    def new_game(
        cls,
        factions: Iterable[Faction] | None = None,
        seed: int | None = None,
    ) -> "GameState":
        ordered: list[Faction] = list(factions) if factions else [
            Faction.MARQUISE,
            Faction.EYRIE,
            Faction.ALLIANCE,
            Faction.VAGABOND,
        ]
        seat_count = len(ordered)
        if seat_count < 2 or seat_count > 6:
            raise ValueError("Root supports 2-6 players (Law 5).")
        remove_dominance = seat_count == 2

        board = Board.autumn_map()
        players: dict[Faction, FactionState] = {}
        for faction in ordered:
            if faction == Faction.MARQUISE:
                players[faction] = MarquiseState(faction=Faction.MARQUISE)
            elif faction == Faction.EYRIE:
                players[faction] = EyrieState(faction=Faction.EYRIE)
            elif faction == Faction.ALLIANCE:
                players[faction] = AllianceState(faction=Faction.ALLIANCE)
            elif faction == Faction.VAGABOND:
                players[faction] = VagabondState(faction=Faction.VAGABOND)
            else:
                raise NotImplementedError(
                    f"Faction {faction.name} is not implemented in the base-game module."
                )

        deck = shuffled_deck(seed=seed, remove_dominance=remove_dominance)
        state = cls(
            board=board,
            players=players,
            turn_order=ordered,
            deck=deck,
            seat_count=seat_count,
        )
        state.deal_starting_hands()
        return state

    # Hand / deck --------------------------------------------------------
    def draw_card(self, faction: Faction) -> Card | None:
        if not self.deck:
            self.reshuffle_discard()
        if not self.deck:
            return None
        card = self.deck.pop()
        self.players[faction].hand.append(card)
        return card

    def deal_starting_hands(self, hand_size: int = 3) -> None:
        for _ in range(hand_size):
            for faction in self.turn_order:
                self.draw_card(faction)

    def reshuffle_discard(self) -> None:
        if not self.discard_pile:
            return
        self.deck = self.discard_pile
        self.discard_pile = []
        # Caller provides RNG when needed via RulesEngine; otherwise stable
        # ordering is acceptable for testing.

    def discard(self, card: Card) -> None:
        self.discard_pile.append(card)

    # Turn / phase -------------------------------------------------------
    @property
    def current_faction(self) -> Faction:
        return self.turn_order[self.current_turn_index]

    def faction_state(self, faction: Faction) -> FactionState:
        return self.players[faction]

    def advance_phase(self) -> None:
        if self.current_phase == Phase.BIRDSONG:
            self.current_phase = Phase.DAYLIGHT
        elif self.current_phase == Phase.DAYLIGHT:
            self.current_phase = Phase.EVENING
        else:
            self.current_phase = Phase.BIRDSONG
            self.current_turn_index = (self.current_turn_index + 1) % self.seat_count
            self.turn_count += 1

    def append_log(self, message: str) -> None:
        self.log.append(message)
        if len(self.log) > 200:
            del self.log[: len(self.log) - 200]
