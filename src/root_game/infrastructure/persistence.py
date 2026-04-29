"""Save/load utilities (snapshot of human-relevant state).

Note: the rewrite of the game state significantly expands what is
serialized. For safety we persist a high-level snapshot suitable for
inspection rather than perfect round-tripping; full save/load is a
follow-up.
"""

import json
from pathlib import Path

from root_game.domain.enums import Faction, Phase
from root_game.domain.state import GameState


def save_snapshot(state: GameState, path: str | Path) -> None:
    payload = {
        "turn_count": state.turn_count,
        "current_phase": state.current_phase.name,
        "current_faction": state.current_faction.name,
        "winner": state.winner.name if state.winner else None,
        "players": {
            faction.name: {
                "vp": player.victory_points,
                "hand_size": len(player.hand),
                "items": [it.name for it in player.crafted_items],
                "persistent": sorted(player.persistent_effects),
            }
            for faction, player in state.players.items()
        },
        "board": {
            cid: {
                "suit": clearing.suit.name,
                "warriors": {f.name: n for f, n in clearing.warriors.items() if n > 0},
                "buildings": [
                    f"{o.name if o else 'NEUTRAL'}:{kind.name}"
                    for o, kind in clearing.buildings
                ],
                "tokens": [f"{f.name}:{t.name}" for f, t in clearing.tokens],
            }
            for cid, clearing in state.board.clearings.items()
        },
    }
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_snapshot(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
