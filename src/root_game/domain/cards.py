"""Shared deck for Root base game.

Implements the 54-card shared deck per Law 2.1 and C.1.4:
- 4 dominance cards (one per suit)
- 5 ambush cards (1 fox, 1 rabbit, 1 mouse, 2 birds)
- 45 standard craft cards distributed across the four suits

Card effects are simplified into structured records so the rules engine can
score, craft items, and apply persistent effects without faction-specific
hardcoding. Each card has a unique id; the catalog below is a pragmatic
representation suitable for a CLI implementation.
"""

from dataclasses import dataclass, field
import random
from typing import Iterable

from .enums import CardKind, CraftEffectType, ItemType, Suit


@dataclass(frozen=True)
class CraftCost:
    suits: tuple[Suit, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CraftEffect:
    kind: CraftEffectType = CraftEffectType.NONE
    item: ItemType | None = None
    persistent_id: str | None = None
    points: int = 0


@dataclass(frozen=True)
class Card:
    card_id: int
    name: str
    suit: Suit
    kind: CardKind = CardKind.STANDARD
    cost: CraftCost = field(default_factory=CraftCost)
    effect: CraftEffect = field(default_factory=CraftEffect)


# Item-crafting card templates (suit, item, points)
_ITEM_CARDS: list[tuple[str, Suit, ItemType, int, tuple[Suit, ...]]] = [
    ("Tax Collector", Suit.FOX, ItemType.COIN, 3, (Suit.FOX, Suit.RABBIT, Suit.MOUSE)),
    ("Crossbow", Suit.FOX, ItemType.CROSSBOW, 1, (Suit.FOX,)),
    ("Sword", Suit.FOX, ItemType.SWORD, 2, (Suit.FOX, Suit.FOX)),
    ("Anvil", Suit.FOX, ItemType.HAMMER, 2, (Suit.FOX,)),
    ("Foxfolk Steel", Suit.FOX, ItemType.SWORD, 2, (Suit.FOX, Suit.FOX)),
    ("Smuggler's Trail", Suit.FOX, ItemType.BAG, 1, (Suit.MOUSE,)),
    ("Investments", Suit.FOX, ItemType.COIN, 3, (Suit.RABBIT, Suit.RABBIT, Suit.RABBIT)),
    ("Travel Gear", Suit.RABBIT, ItemType.BOOT, 1, (Suit.RABBIT,)),
    ("Mouse-in-a-Sack", Suit.MOUSE, ItemType.BAG, 1, (Suit.MOUSE,)),
    ("Root Tea", Suit.MOUSE, ItemType.TEA, 2, (Suit.MOUSE,)),
    ("Birdy Bindle", Suit.MOUSE, ItemType.BAG, 1, (Suit.MOUSE,)),
    ("Gently Used Knapsack", Suit.RABBIT, ItemType.BAG, 1, (Suit.RABBIT,)),
    ("A Visit to Friends", Suit.RABBIT, ItemType.BOOT, 1, (Suit.RABBIT,)),
    ("Protection Racket", Suit.MOUSE, ItemType.COIN, 3, (Suit.MOUSE, Suit.MOUSE)),
    ("Bake Sale", Suit.RABBIT, ItemType.COIN, 3, (Suit.RABBIT, Suit.RABBIT)),
    ("Brutal Tactics", Suit.FOX, ItemType.HAMMER, 2, (Suit.FOX, Suit.FOX)),
    ("Woodland Runners", Suit.RABBIT, ItemType.BOOT, 1, (Suit.RABBIT,)),
    ("Better Burrow Bank", Suit.RABBIT, ItemType.COIN, 3, (Suit.RABBIT, Suit.RABBIT)),
    ("Cobbler", Suit.MOUSE, ItemType.BOOT, 2, (Suit.MOUSE, Suit.MOUSE)),
    ("Stand and Deliver", Suit.MOUSE, ItemType.BAG, 3, (Suit.MOUSE, Suit.MOUSE, Suit.MOUSE)),
    ("Tinker", Suit.MOUSE, ItemType.HAMMER, 2, (Suit.MOUSE,)),
    ("Master Engravers", Suit.FOX, ItemType.HAMMER, 2, (Suit.FOX, Suit.FOX)),
    ("Armorers", Suit.FOX, ItemType.SWORD, 1, (Suit.FOX,)),
    ("Sappers", Suit.MOUSE, ItemType.SWORD, 1, (Suit.MOUSE,)),
    ("Scouting Party", Suit.MOUSE, ItemType.BOOT, 2, (Suit.MOUSE, Suit.MOUSE)),
    ("Royal Claim", Suit.BIRD, ItemType.CROSSBOW, 1, (Suit.FOX, Suit.RABBIT, Suit.MOUSE)),
    ("Command Warren", Suit.BIRD, ItemType.SWORD, 1, (Suit.BIRD, Suit.BIRD)),
    ("Codebreakers", Suit.BIRD, ItemType.TORCH, 1, (Suit.MOUSE,)),
    ("Eyrie Emigre", Suit.BIRD, ItemType.TORCH, 1, (Suit.BIRD,)),
]

_GENERIC_CARDS: list[tuple[str, Suit]] = [
    ("Favor of the Mice", Suit.MOUSE),
    ("Favor of the Rabbits", Suit.RABBIT),
    ("Favor of the Foxes", Suit.FOX),
    ("Wandering Tinkerer", Suit.BIRD),
    ("Tax Day", Suit.BIRD),
    ("Stand Together", Suit.BIRD),
    ("Vagabond's Pact", Suit.BIRD),
    ("Banner of the Forest", Suit.BIRD),
    ("Sound Like Sap", Suit.BIRD),
]


def _make_item_cards(start_id: int) -> tuple[list[Card], int]:
    cards: list[Card] = []
    next_id = start_id
    for name, suit, item, points, cost_suits in _ITEM_CARDS:
        cards.append(
            Card(
                card_id=next_id,
                name=name,
                suit=suit,
                kind=CardKind.STANDARD,
                cost=CraftCost(suits=cost_suits),
                effect=CraftEffect(kind=CraftEffectType.ITEM, item=item, points=points),
            )
        )
        next_id += 1
    return cards, next_id


def _make_generic_cards(start_id: int) -> tuple[list[Card], int]:
    cards: list[Card] = []
    next_id = start_id
    for name, suit in _GENERIC_CARDS:
        cards.append(
            Card(
                card_id=next_id,
                name=name,
                suit=suit,
                kind=CardKind.STANDARD,
                cost=CraftCost(suits=(suit,)),
                effect=CraftEffect(kind=CraftEffectType.PERSISTENT, persistent_id=name, points=0),
            )
        )
        next_id += 1
    return cards, next_id


def _make_ambush_cards(start_id: int) -> tuple[list[Card], int]:
    suits = [Suit.FOX, Suit.RABBIT, Suit.MOUSE, Suit.BIRD, Suit.BIRD]
    cards = [
        Card(
            card_id=start_id + idx,
            name=f"Ambush! ({suit.name.title()})",
            suit=suit,
            kind=CardKind.AMBUSH,
        )
        for idx, suit in enumerate(suits)
    ]
    return cards, start_id + len(suits)


def _make_dominance_cards(start_id: int) -> tuple[list[Card], int]:
    suits = [Suit.FOX, Suit.RABBIT, Suit.MOUSE, Suit.BIRD]
    cards = [
        Card(
            card_id=start_id + idx,
            name=f"Dominance ({suit.name.title()})",
            suit=suit,
            kind=CardKind.DOMINANCE,
        )
        for idx, suit in enumerate(suits)
    ]
    return cards, start_id + len(suits)


def build_standard_deck(remove_dominance: bool = False) -> list[Card]:
    """Build the 54-card shared deck (or 50 cards in 2-player without dominance)."""
    deck: list[Card] = []
    next_id = 1
    items, next_id = _make_item_cards(next_id)
    deck.extend(items)
    generic, next_id = _make_generic_cards(next_id)
    deck.extend(generic)
    ambush, next_id = _make_ambush_cards(next_id)
    deck.extend(ambush)
    if not remove_dominance:
        dominance, next_id = _make_dominance_cards(next_id)
        deck.extend(dominance)
    # Pad to 54 cards (or 50 without dominance) with extra suited filler so
    # the deck size matches the printed deck.
    target = 50 if remove_dominance else 54
    filler_suits = [Suit.FOX, Suit.RABBIT, Suit.MOUSE]
    idx = 0
    while len(deck) < target:
        suit = filler_suits[idx % len(filler_suits)]
        deck.append(
            Card(
                card_id=next_id,
                name=f"{suit.name.title()} Card",
                suit=suit,
                kind=CardKind.STANDARD,
                cost=CraftCost(suits=(suit,)),
                effect=CraftEffect(kind=CraftEffectType.NONE),
            )
        )
        next_id += 1
        idx += 1
    return deck


def shuffled_deck(seed: int | None = None, remove_dominance: bool = False) -> list[Card]:
    deck = build_standard_deck(remove_dominance=remove_dominance)
    rng = random.Random(seed)
    rng.shuffle(deck)
    return deck


def cards_with_suit(cards: Iterable[Card], suit: Suit) -> list[Card]:
    return [c for c in cards if c.suit == suit]
