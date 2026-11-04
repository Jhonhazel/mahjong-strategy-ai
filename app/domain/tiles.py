"""Canonical Botzone/PyMahjongGB tile order; flowers are never model targets."""
import random
from collections.abc import Iterable
from numbers import Integral

from app.domain.exceptions import IllegalActionError

NUM_TILE_TYPES = 34
GRID_ROWS, GRID_COLS, GRID_CELLS = 4, 9, 36
NUMBERED_SUITS = "WTB"
TILE_LIST = tuple(f"{s}{n}" for s in NUMBERED_SUITS for n in range(1, 10)) + tuple(f"F{n}" for n in range(1, 5)) + tuple(f"J{n}" for n in range(1, 4))
TILE_TO_INDEX = {tile: i for i, tile in enumerate(TILE_LIST)}
FLOWER_TILES = tuple(f"H{n}" for n in range(1, 9))


def is_flower_tile(tile: str) -> bool:
    return tile in FLOWER_TILES


def tile_to_index(tile: str) -> int:
    if not isinstance(tile, str) or tile not in TILE_TO_INDEX:
        raise IllegalActionError(f"Invalid normal tile: {tile!r}")
    return TILE_TO_INDEX[tile]


def index_to_tile(idx: int) -> str:
    if isinstance(idx, bool) or not isinstance(idx, Integral) or not 0 <= idx < NUM_TILE_TYPES:
        raise IllegalActionError(f"Tile index must be 0..33: {idx!r}")
    return TILE_LIST[int(idx)]


def tile_to_grid_rc(tile: str) -> tuple[int, int]:
    return divmod(tile_to_index(tile), GRID_COLS)


def sort_hand_tiles(tiles: Iterable[str]) -> list[str]:
    return sorted(tiles, key=tile_to_index)


def build_standard_136_wall(seed: int) -> list[str]:
    wall = [t for t in TILE_LIST for _ in range(4)]
    random.Random(seed).shuffle(wall)
    return wall


def build_144_wall_with_flowers(seed: int) -> list[str]:
    wall = [t for t in TILE_LIST for _ in range(4)] + list(FLOWER_TILES)
    random.Random(seed).shuffle(wall)
    return wall
