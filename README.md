# Root_Project

Python implementation of the board game **Root** (base game) following the
Law of Root (October 13, 2025). CLI-first, with a clean Controller +
GameService architecture so a GUI or AI can be added later without
rewriting the rules engine.

## Scope of base-game logic

Implemented per Law sections 1-9:

- Standard 12-clearing autumn map with 4 corner clearings and 4 ruins.
- 54-card shared deck (50 in 2-player, dominance removed).
- Crafting items + persistent effects + dominance + ambush cards.
- Battle resolution (Law 4.3): ambush, dice, defenseless, hits, scoring.
- Marquise de Cat (Law 6) including build cost track, recruit, overwork,
  bird-card extra actions, field hospitals readiness via supply tracking.
- Eyrie Dynasties (Law 7) with leaders, Loyal Viziers, decree resolution
  and turmoil flow.
- Woodland Alliance (Law 8) with supporters, sympathy, revolt, train,
  mobilize, military operations, guerrilla war.
- Vagabond (Law 9) with satchel + tracks, slip, move/battle/strike/aid/
  explore/quest/repair, relationships, characters (Thief/Tinker/Ranger).
- Setup flow with proper Turn 0 ordering (5.1.7): Marquise places keep ->
  starting buildings -> garrison -> Eyrie roost -> leader -> Alliance
  draws supporters -> Vagabond character + forest placement.
- Victory: 30 VP and dominance card win conditions.

## Project Layout

```
src/root_game/
  domain/           # Pure rules and data models
    board.py            # Autumn map, clearings, paths, forests
    cards.py            # 54-card deck builder
    enums.py            # Suits, factions, items, phases, etc.
    actions.py          # UI-agnostic Action contract
    state.py            # Top-level GameState
    faction_state.py    # Per-faction state records
    factions.py         # Faction phase hooks + legal action generators
    battle.py           # Battle resolution per Law 4.3
    rules.py            # Rules engine: dispatch, validation, victory
  application/
    controllers.py      # Controller protocol + bot/cli stubs
    service.py          # GameService that wires controllers to engine
  interfaces/
    cli/adapter.py      # Hot-seat CLI adapter
    gui/contracts.py    # Protocols for a future GUI adapter
  infrastructure/
    persistence.py      # JSON snapshot save/load
  main.py
```

## Architecture

```
+-----------------+      +-----------------+
|   CLI / GUI     |----->|  Controllers    |
+-----------------+      +-----------------+
                                 |
                                 v
                         +-----------------+
                         |  GameService    |
                         +-----------------+
                                 |
                                 v
                         +-----------------+
                         |  RulesEngine    |
                         +-----------------+
                                 |
              +------------------+------------------+
              |                  |                  |
              v                  v                  v
        Faction systems     Battle / Cards     GameState
```

Controllers decide which legal action to take when their seat is active,
so the same engine drives hot-seat humans now and bots/GUI later.

## Setup (Conda)

```powershell
conda create -n root_game python=3.11 -y
conda activate root_game
pip install -r requirements.txt
pip install -e .
```

## Run

```powershell
python -m root_game.main
```

## Test

```powershell
pytest
```

## Notes / known simplifications

- Card list in `cards.py` is rule-faithful in shape (suits, costs, item
  rewards, ambush, dominance) but not 1:1 to the printed card titles.
- Eyrie decree resolution applies the simplest legal effect; if none is
  available the engine triggers turmoil per Law 7.7.
- Vagabond items, slips, and quests use simplified scoring (1 VP for
  ruins, 1 VP for quests) until the full quest deck is added.
- Persistence saves a high-level snapshot only.

These are explicit follow-ups to expand without changing the architecture.
