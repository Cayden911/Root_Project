from root_game.application.controllers import FirstActionController
from root_game.application.service import GameService
from root_game.domain.actions import (
    A_END_PHASE,
    A_EYRIE_ADD_TO_DECREE,
    Action,
)
from root_game.domain.cards import Card
from root_game.domain.enums import (
    CardKind,
    DecreeColumn,
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
