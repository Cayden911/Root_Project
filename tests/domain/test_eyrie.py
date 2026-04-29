from root_game.application.controllers import FirstActionController
from root_game.application.service import GameService
from root_game.domain.actions import (
    A_END_PHASE,
    A_EYRIE_ADD_TO_DECREE,
    A_EYRIE_RESOLVE_DECREE_CARD,
    Action,
)
from root_game.domain.cards import Card
from root_game.domain.enums import (
    BuildingType,
    CardKind,
    DecreeColumn,
    EyrieLeader,
    Faction,
    Phase,
    Suit,
)
from root_game.domain.faction_state import EyrieState


def _service_in_eyrie_birdsong() -> GameService:
    factions = [Faction.MARQUISE, Faction.EYRIE, Faction.ALLIANCE, Faction.VAGABOND]
    service = GameService(
        controllers={f: FirstActionController() for f in factions},
        factions=factions,
        seed=21,
    )
    safety = 80
    while not service.state.setup_complete and safety > 0:
        service.step()
        safety -= 1
    while not (
        service.state.turn_order[service.state.current_turn_index] == Faction.EYRIE
        and service.state.current_phase == Phase.BIRDSONG
    ):
        service.step()
        safety -= 1
        if safety <= 0:
            raise AssertionError("Could not reach Eyrie Birdsong")
    return service


def _stack_eyrie_hand(es: EyrieState) -> None:
    es.hand = [
        Card(card_id=900, name="Fox A", suit=Suit.FOX, kind=CardKind.STANDARD),
        Card(card_id=901, name="Fox B", suit=Suit.FOX, kind=CardKind.STANDARD),
        Card(card_id=902, name="Fox C", suit=Suit.FOX, kind=CardKind.STANDARD),
        Card(card_id=910, name="Bird X", suit=Suit.BIRD, kind=CardKind.STANDARD),
        Card(card_id=911, name="Bird Y", suit=Suit.BIRD, kind=CardKind.STANDARD),
    ]


def test_eyrie_decree_max_two_cards_per_birdsong() -> None:
    service = _service_in_eyrie_birdsong()
    es = service.state.players[Faction.EYRIE]
    assert isinstance(es, EyrieState)
    _stack_eyrie_hand(es)

    service.rules.execute(
        service.state,
        Action(Faction.EYRIE, A_EYRIE_ADD_TO_DECREE,
               {"column": DecreeColumn.RECRUIT.name, "card": 900}),
    )
    service.rules.execute(
        service.state,
        Action(Faction.EYRIE, A_EYRIE_ADD_TO_DECREE,
               {"column": DecreeColumn.MOVE.name, "card": 901}),
    )
    legal = service.rules.legal_actions(service.state, Faction.EYRIE)
    add_actions = [a for a in legal if a.action_type == A_EYRIE_ADD_TO_DECREE]
    assert add_actions == [], (
        "After 2 adds, no more Add-to-Decree actions should be legal"
    )
    assert any(a.action_type == A_END_PHASE for a in legal)


def test_eyrie_decree_max_one_bird_per_birdsong() -> None:
    service = _service_in_eyrie_birdsong()
    es = service.state.players[Faction.EYRIE]
    assert isinstance(es, EyrieState)
    _stack_eyrie_hand(es)

    service.rules.execute(
        service.state,
        Action(Faction.EYRIE, A_EYRIE_ADD_TO_DECREE,
               {"column": DecreeColumn.MOVE.name, "card": 910}),
    )
    legal = service.rules.legal_actions(service.state, Faction.EYRIE)
    add_actions = [a for a in legal if a.action_type == A_EYRIE_ADD_TO_DECREE]
    assert add_actions, "Eyrie should still have one add remaining after 1 add"
    bird_card_ids = {911}
    for a in add_actions:
        assert a.payload["card"] not in bird_card_ids, (
            "After adding a bird, no further bird cards should be offered"
        )


def _add_card_to_decree(es: EyrieState, col: DecreeColumn, card: Card) -> None:
    """Stuff a card directly into the decree, bypassing per-Birdsong limits."""
    es.decree[col].append(card)


def test_decree_resolution_must_be_left_to_right_in_legal_actions() -> None:
    service = _service_in_eyrie_birdsong()
    state = service.state
    es = state.players[Faction.EYRIE]
    assert isinstance(es, EyrieState)
    while service.state.current_phase != Phase.DAYLIGHT:
        legal = service.rules.legal_actions(state, Faction.EYRIE)
        end = next(a for a in legal if a.action_type == A_END_PHASE)
        service.rules.execute(state, end)

    _add_card_to_decree(es, DecreeColumn.RECRUIT,
        Card(card_id=920, name="Fox R", suit=Suit.FOX, kind=CardKind.STANDARD))
    _add_card_to_decree(es, DecreeColumn.MOVE,
        Card(card_id=921, name="Fox M", suit=Suit.FOX, kind=CardKind.STANDARD))
    _add_card_to_decree(es, DecreeColumn.BATTLE,
        Card(card_id=922, name="Fox X", suit=Suit.FOX, kind=CardKind.STANDARD))
    _add_card_to_decree(es, DecreeColumn.BUILD,
        Card(card_id=923, name="Fox B", suit=Suit.FOX, kind=CardKind.STANDARD))

    legal = service.rules.legal_actions(state, Faction.EYRIE)
    resolves = [a for a in legal if a.action_type == A_EYRIE_RESOLVE_DECREE_CARD]
    assert len(resolves) == 1, "Only one column should be offered at a time"
    assert resolves[0].payload["column"] == DecreeColumn.RECRUIT.name


def test_decree_resolution_handler_rejects_out_of_order() -> None:
    service = _service_in_eyrie_birdsong()
    state = service.state
    es = state.players[Faction.EYRIE]
    assert isinstance(es, EyrieState)
    while service.state.current_phase != Phase.DAYLIGHT:
        legal = service.rules.legal_actions(state, Faction.EYRIE)
        end = next(a for a in legal if a.action_type == A_END_PHASE)
        service.rules.execute(state, end)

    _add_card_to_decree(es, DecreeColumn.RECRUIT,
        Card(card_id=930, name="R", suit=Suit.FOX, kind=CardKind.STANDARD))
    _add_card_to_decree(es, DecreeColumn.MOVE,
        Card(card_id=931, name="M", suit=Suit.FOX, kind=CardKind.STANDARD))

    try:
        service.rules.execute(
            state,
            Action(Faction.EYRIE, A_EYRIE_RESOLVE_DECREE_CARD,
                   {"column": DecreeColumn.MOVE.name}),
        )
    except ValueError:
        return
    raise AssertionError("Resolving Move before Recruit should have raised")


def _advance_to_eyrie_daylight(service: GameService) -> None:
    state = service.state
    while state.current_phase != Phase.DAYLIGHT:
        legal = service.rules.legal_actions(state, Faction.EYRIE)
        end = next(a for a in legal if a.action_type == A_END_PHASE)
        service.rules.execute(state, end)


def _ensure_matching_roost(service: GameService, suit: Suit) -> None:
    """Make sure there's an Eyrie roost in a matching clearing so the
    auto-recruit helper can place warriors deterministically."""
    state = service.state
    for clearing in state.board.clearings.values():
        if clearing.suit == suit and not any(
            owner == Faction.EYRIE and kind == BuildingType.ROOST
            for owner, kind in clearing.buildings
        ):
            if clearing.open_slots() > 0:
                clearing.place_building(Faction.EYRIE, BuildingType.ROOST)
                state.players[Faction.EYRIE].roosts_remaining -= 1
                return


def _set_decree(es: EyrieState, **cards_per_col: list[Card]) -> None:
    """Replace the entire Decree with the given cards (clears Loyal Viziers)."""
    for col in DecreeColumn:
        es.decree[col] = []
    for col_name, cards in cards_per_col.items():
        es.decree[DecreeColumn[col_name]] = list(cards)


def test_decree_cards_remain_in_column_after_resolution() -> None:
    service = _service_in_eyrie_birdsong()
    state = service.state
    es = state.players[Faction.EYRIE]
    assert isinstance(es, EyrieState)

    fox_card = Card(card_id=950, name="Fox R1", suit=Suit.FOX, kind=CardKind.STANDARD)
    _set_decree(es, RECRUIT=[fox_card])
    _advance_to_eyrie_daylight(service)
    _ensure_matching_roost(service, Suit.FOX)

    service.rules.execute(
        state,
        Action(Faction.EYRIE, A_EYRIE_RESOLVE_DECREE_CARD,
               {"column": DecreeColumn.RECRUIT.name}),
    )
    assert fox_card in es.decree[DecreeColumn.RECRUIT], (
        "Card should remain in the Decree column after resolution"
    )
    assert es.decree_resolved_this_turn[DecreeColumn.RECRUIT] == 1


def test_recruit_limited_to_card_count_per_turn() -> None:
    service = _service_in_eyrie_birdsong()
    state = service.state
    es = state.players[Faction.EYRIE]
    assert isinstance(es, EyrieState)

    _set_decree(es, RECRUIT=[
        Card(card_id=960, name="Fox R", suit=Suit.FOX, kind=CardKind.STANDARD)
    ])
    _advance_to_eyrie_daylight(service)
    _ensure_matching_roost(service, Suit.FOX)

    service.rules.execute(
        state,
        Action(Faction.EYRIE, A_EYRIE_RESOLVE_DECREE_CARD,
               {"column": DecreeColumn.RECRUIT.name}),
    )
    legal = service.rules.legal_actions(state, Faction.EYRIE)
    resolves = [a for a in legal if a.action_type == A_EYRIE_RESOLVE_DECREE_CARD]
    assert resolves == [], (
        "After all Recruit cards are serviced, no more recruit resolutions"
    )
    try:
        service.rules.execute(
            state,
            Action(Faction.EYRIE, A_EYRIE_RESOLVE_DECREE_CARD,
                   {"column": DecreeColumn.RECRUIT.name}),
        )
    except ValueError:
        return
    raise AssertionError(
        "A second recruit on a single-card column should have raised"
    )


def test_charismatic_leader_recruits_two_warriors_per_card() -> None:
    service = _service_in_eyrie_birdsong()
    state = service.state
    es = state.players[Faction.EYRIE]
    assert isinstance(es, EyrieState)
    es.leader = EyrieLeader.CHARISMATIC

    _set_decree(es, RECRUIT=[
        Card(card_id=970, name="Fox R", suit=Suit.FOX, kind=CardKind.STANDARD)
    ])
    _advance_to_eyrie_daylight(service)
    _ensure_matching_roost(service, Suit.FOX)

    target = next(
        c for c in state.board.clearings.values()
        if c.suit == Suit.FOX and any(
            owner == Faction.EYRIE and kind == BuildingType.ROOST
            for owner, kind in c.buildings
        )
    )
    before = target.warriors.get(Faction.EYRIE, 0)
    supply_before = es.warriors_in_supply

    service.rules.execute(
        state,
        Action(Faction.EYRIE, A_EYRIE_RESOLVE_DECREE_CARD,
               {"column": DecreeColumn.RECRUIT.name}),
    )
    after = target.warriors.get(Faction.EYRIE, 0)
    assert after - before == 2, (
        f"Charismatic should recruit 2 warriors, got {after - before}"
    )
    assert supply_before - es.warriors_in_supply == 2


def test_eyrie_decree_handler_rejects_third_add() -> None:
    service = _service_in_eyrie_birdsong()
    es = service.state.players[Faction.EYRIE]
    assert isinstance(es, EyrieState)
    _stack_eyrie_hand(es)

    service.rules.execute(
        service.state,
        Action(Faction.EYRIE, A_EYRIE_ADD_TO_DECREE,
               {"column": DecreeColumn.RECRUIT.name, "card": 900}),
    )
    service.rules.execute(
        service.state,
        Action(Faction.EYRIE, A_EYRIE_ADD_TO_DECREE,
               {"column": DecreeColumn.MOVE.name, "card": 901}),
    )
    try:
        service.rules.execute(
            service.state,
            Action(Faction.EYRIE, A_EYRIE_ADD_TO_DECREE,
                   {"column": DecreeColumn.BUILD.name, "card": 902}),
        )
    except ValueError:
        return
    raise AssertionError("Third Add-to-Decree should have raised ValueError")
