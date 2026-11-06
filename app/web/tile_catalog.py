"""Presentation-only canonical labels. No game rules or legal-action logic."""
from dataclasses import dataclass
from types import MappingProxyType

from app.domain.tiles import TILE_LIST,FLOWER_TILES

WIND_NAMES=('Timur','Selatan','Barat','Utara')


@dataclass(frozen=True)
class TileFace:
    code: str
    label: str
    symbol: str
    kind: str
    rank: int | None


def _face(code):
    suit,rank=code[0],int(code[1])
    kind,label={'W':('characters','Karakter'),'T':('bamboo','Bambu'),'B':('circles','Lingkaran'),
                'F':('wind','Angin'),'J':('dragon','Naga'),'H':('flower','Bunga')}[suit]
    suffix=WIND_NAMES[rank-1] if suit=='F' else ('Merah','Hijau','Putih')[rank-1] if suit=='J' else str(rank)
    return TileFace(code,label+' '+suffix,'tile-'+code,kind,rank)


TILE_CATALOG=MappingProxyType({
    **{code:_face(code) for code in (*TILE_LIST,*FLOWER_TILES)},
    'back':TileFace('back','Tile tertutup','tile-back','back',None),
    'unknown':TileFace('unknown','Tile tidak dikenal','tile-unknown','unknown',None),
})
