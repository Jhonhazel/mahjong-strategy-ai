"""Real saved MLP suggestions during a normal Phase 1 game; no automatic AI move."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import random
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from app.services.ai_prediction_service import AIDiscardPredictionService
from app.services.bot_service import ShantenHeuristicBot
from app.services.game_service import GameSessionService
from training.reporting import write_json_report


def run_demo(checkpoint: Path, seed: int, human_seat: int, finish_round: bool, contract_path: Path = Path("datasets/data_contract.json")):
    contract = json.loads(Path(contract_path).read_text(encoding="utf-8"))
    ai = AIDiscardPredictionService(checkpoint, expected_contract=contract)
    games = GameSessionService()
    helper, rng = ShantenHeuristicBot(), random.Random(seed)
    predictions, actions = [], []
    previous_action = None
    view = games.create_game(seed=seed, human_seat=human_seat)
    try:
        while view.status != "FINISHED":
            if view.status == "WAITING_HUMAN_DISCARD":
                state = games.get_human_encoded_turn(view.game_id)
                before = (state.obs.copy(), state.legal_mask.copy(), state.legal_discard_mask.copy())
                prediction = ai.predict(state)
                unchanged = games.get_player_view(view.game_id) == view and all(np.array_equal(a, b) for a, b in zip(before, (state.obs, state.legal_mask, state.legal_discard_mask)))
                legal = all(state.legal_mask[item.action_id] for item in prediction.top3)
                if not unchanged or not legal:
                    raise RuntimeError("Live prediction mutated state or suggested an illegal discard")
                record = {"turn_number": view.turn_number, "human_seat": human_seat, "turn_phase": "POST_MELD_DISCARD" if previous_action in ("Chi", "Peng") else "SELF_TURN", "own_visible_hand": list(view.own_hand), "legal_discard_mask": state.legal_discard_mask.tolist(), "prediction": asdict(prediction), "state_unchanged": unchanged, "all_suggestions_legal": legal}
                predictions.append(record)
                print(f"Turn {view.turn_number} / {record['turn_phase']} | visible hand: {' '.join(view.own_hand)}")
                print(f"Recommended: {prediction.recommended_tile}, action {prediction.recommended_action_id}")
                print("Top legal scores:", ", ".join(f"{s.tile}={s.score:.6f}" for s in prediction.top3))
                print("State unchanged; scores describe discard behavior, not winning chances.")
                if not finish_round:
                    break
                # Independent normal gameplay policy; the AI recommendation is
                # advisory and is never submitted automatically by predict().
                chosen_id = helper.select_action(state, view.own_hand, view.seat_public_states[human_seat].melds, rng)
                chosen = next(o for o in view.legal_actions if o.action_id == chosen_id)
            else:
                choices = [o for o in view.legal_actions if o.action_type == "Hu"] or [o for o in view.legal_actions if o.action_type in ("Chi", "Peng")] or list(view.legal_actions)
                chosen = choices[0]
            actions.append({"turn_number": view.turn_number, "action_id": chosen.action_id, "action_type": chosen.action_type})
            previous_action = chosen.action_type
            view = games.submit_human_action(view.game_id, chosen.action_id, view.turn_number)
        if not predictions:
            raise RuntimeError("The selected seed finished without a human discard prediction")
        return {"status": view.status, "seed": seed, "human_seat": human_seat, "model_version": ai.model_version, "encoder_version": ai.encoder_version, "predictions": predictions, "human_actions": actions, "turn_number": view.turn_number, "round_result": asdict(view.round_result) if view.round_result else None, "prediction_is_advisory": True}
    finally:
        games.shutdown()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, default=Path("artifacts/models/mahjong_discard_mlp.pt"))
    parser.add_argument("--contract", type=Path, default=Path("datasets/data_contract.json"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--human-seat", type=int, choices=range(4), default=1)
    parser.add_argument("--finish-round", action="store_true")
    parser.add_argument("--smoke", action="store_true", help="Complete the real round using the deterministic seed and normal gameplay policy")
    parser.add_argument("--output", type=Path, default=Path("artifacts/phase2/live_demo.json"))
    args = parser.parse_args()
    report = run_demo(args.checkpoint, args.seed, args.human_seat, args.finish_round or args.smoke, args.contract)
    write_json_report(args.output, report)
    print(f"Game {report['status']}; predictions={len(report['predictions'])}; turn={report['turn_number']}")


if __name__ == "__main__":
    main()
