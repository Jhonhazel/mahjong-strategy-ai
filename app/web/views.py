"""Explicit public allowlists; no referee objects or __dict__ serialization."""
from app.web.schemas import GameViewOut, HistorySummaryOut, HistoryDetailOut, SavedPredictionOut


def safe_player_view(view):
    result=view.round_result
    final=None if result is None else dict(ending=result.ending,outcome_type=result.outcome_type,
        winner_seat=result.winner_seat,discarder_seat=result.discarder_seat,qianggang=result.qianggang,
        win_tile=result.win_tile,total_fan=result.total_fan,score_deltas=list(result.score_deltas),
        fans=[dict(fan_points=f.fan_points,count=f.count,fan_name_zh=f.fan_name_zh,fan_name_en=f.fan_name_en) for f in result.fans])
    return GameViewOut(game_id=view.game_id,status=view.status,human_seat=view.human_seat,
        prevalent_wind=view.prevalent_wind,active_seat=view.active_seat,turn_number=view.turn_number,
        wall_tiles_remaining=view.wall_tiles_remaining,own_hand=list(view.own_hand),own_flowers=list(view.own_flowers),
        seat_public_states=[dict(seat=s.seat,concealed_count=s.concealed_count,flowers=list(s.flowers),
            discards=list(s.discards),wall_remaining=s.wall_remaining,
            melds=[dict(pack_type=p.pack_type,offer=p.offer,
                        tile=None if p.pack_type=='ANGANG' and s.seat!=view.human_seat else p.tile) for p in s.melds]) for s in view.seat_public_states],
        legal_actions=[dict(action_id=a.action_id,action_type=a.action_type,tile=a.tile,
                            meld_tiles=None if a.meld_tiles is None else list(a.meld_tiles),label=a.label) for a in view.legal_actions],
        can_request_ai_prediction=view.can_request_ai_prediction,round_result=final)


def history_summary(record):
    return HistorySummaryOut(prediction_id=record.id,game_id=record.game_id,turn_number=record.turn_number,
        turn_phase=record.turn_phase,created_at=record.created_at,model_version=record.model_version,
        encoder_version=record.encoder_version,recommended_tile=record.output_snapshot['recommended_tile'],
        top3=record.output_snapshot['top3'])


def history_detail(record):
    return HistoryDetailOut(**history_summary(record).model_dump(),input_snapshot=record.input_snapshot,
                            output_snapshot=record.output_snapshot,checkpoint_sha256=record.checkpoint_sha256,
                            state_digest=record.state_digest)


def saved_prediction(record,reused):
    return SavedPredictionOut(**record.output_snapshot,prediction_id=record.id,game_id=record.game_id,
                              turn_phase=record.turn_phase,reused=reused)
