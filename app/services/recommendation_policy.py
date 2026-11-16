"""Presentation policy over original legal-discard probabilities, never a new model."""
from dataclasses import dataclass
import math
from numbers import Real

from app.domain.tiles import index_to_tile


@dataclass(frozen=True)
class RecommendationPolicy:
    minimum_score: float = 0.10
    maximum_suggestions: int = 3

    @property
    def minimum_label(self):
        return f'{self.minimum_score*100:g}%'

    @property
    def game_empty_message(self):
        return f'Belum ada saran yang memenuhi batas minimal {self.minimum_label} pada giliran ini. Anda tetap dapat memilih tile yang ingin dibuang.'

    @property
    def history_empty_message(self):
        return f'Pada giliran ini, belum ada saran yang memenuhi batas minimal {self.minimum_label}.'


RECOMMENDATION_POLICY = RecommendationPolicy()


def filter_recommendations(scores, legal_discard_mask):
    """Validate a full distribution and project 0..max suggestions without rescaling."""
    scores=tuple(scores);legal=tuple(legal_discard_mask)
    if (len(scores)!=34 or len(legal)!=34 or any(type(value) is not bool for value in legal)
            or not any(legal) or any(isinstance(value,bool) or not isinstance(value,Real)
                or not math.isfinite(value) or not 0<=value<=1 for value in scores)
            or not math.isclose(sum(scores),1.,abs_tol=1e-5)
            or any(value!=0. for value,allowed in zip(scores,legal) if not allowed)):
        raise ValueError('Expected a normalized distribution over legal discards')
    policy=RECOMMENDATION_POLICY
    # Stable class order is the existing rank_legal_classes tie-breaking rule.
    ranking=sorted((i for i in range(34) if legal[i] and scores[i]>=policy.minimum_score),
                   key=lambda i:(-scores[i],i))[:policy.maximum_suggestions]
    suggestions=[{'tile':index_to_tile(i),'class_index':i,'action_id':i+2,'score':float(scores[i])} for i in ranking]
    return {'suggestions':suggestions,'minimum_score':policy.minimum_score,
            'maximum_suggestions':policy.maximum_suggestions,
            'status':'available' if suggestions else 'no_suggestions'}
