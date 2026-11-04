"""One human vs three local shanten bots. No model or prediction in Phase 1."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import random
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.actions import decode_action
from app.domain.exceptions import MahjongError
from app.services.bot_service import ShantenHeuristicBot
from app.services.game_service import GameSessionService


def display(view):
    print(f"\nTurn {view.turn_number} | {view.status} | active={view.active_seat} | wall={view.wall_tiles_remaining}")
    print("Your hand:", " ".join(view.own_hand))
    for player in view.seat_public_states:
        melds = [f"{m.pack_type}:{m.tile or '[concealed]'}" for m in player.melds]
        print(f"Seat {player.seat}: concealed={player.concealed_count} melds={melds} flowers={list(player.flowers)} discards={' '.join(player.discards)}")
    if view.legal_actions:
        print("Actions:", " | ".join(f"{o.action_id}: {o.label}" for o in view.legal_actions))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--human-seat", type=int, choices=range(4), default=0)
    parser.add_argument("--flowers", action="store_true")
    parser.add_argument("--auto-human-demo", action="store_true", help="Real service/referee round, automatically select human actions")
    parser.add_argument("--output", type=Path, help="Write final JSON evidence")
    args = parser.parse_args()
    service = GameSessionService()
    view = service.create_game(args.human_seat, seed=args.seed, include_flowers=args.flowers)
    human_bot, rng, decisions = ShantenHeuristicBot(), random.Random(args.seed), 0
    try:
        while view.status != "FINISHED":
            display(view)
            if args.auto_human_demo:
                if view.status == "WAITING_HUMAN_CLAIM":
                    ids = [o.action_id for o in view.legal_actions]
                    action = 1 if 1 in ids else 0
                else:
                    # Own visible packs are provided; no access to opponent hands.
                    action = human_bot.select_action(service.get_human_encoded_turn(view.game_id), view.own_hand, view.seat_public_states[view.human_seat].melds, rng)
                print("Auto human:", action, decode_action(action).action_type)
            else:
                try:
                    action = int(input("Action ID: "))
                except ValueError:
                    print("Enter one of the displayed action IDs.")
                    continue
            try:
                view = service.submit_human_action(view.game_id, action, view.turn_number)
                decisions += 1
            except MahjongError as exc:
                if args.auto_human_demo:
                    raise
                print(str(exc))
        display(view)
        report = asdict(view)
        report.update(seed=args.seed, human_decisions=decisions, mode="automated_human" if args.auto_human_demo else "interactive")
        print(json.dumps(report["round_result"], ensure_ascii=False, indent=2))
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    finally:
        service.shutdown()


if __name__ == "__main__":
    main()
