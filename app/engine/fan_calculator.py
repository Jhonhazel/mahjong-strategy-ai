"""Validated boundary to PyMahjongGB; unexpected failures are never Hu=False."""
from collections import Counter
from collections.abc import Sequence
from numbers import Integral

from MahjongGB import MahjongFanCalculator, MahjongShanten

from app.domain.exceptions import EngineInvariantError, IllegalActionError
from app.domain.models import FanItem, LibraryPack, MeldPack, RoundEnding
from app.domain.tiles import tile_to_index

MIN_MCR_FAN = 8


def _int_range(value, lower, upper):
    return not isinstance(value, bool) and isinstance(value, Integral) and lower <= value <= upper


class FanCalculatorAdapter:
    @staticmethod
    def normalize_packs_for_gb(packs: Sequence[LibraryPack | MeldPack]) -> tuple[LibraryPack, ...]:
        result = []
        for pack in packs:
            try:
                kind, tile, offer = pack.as_library_pack() if isinstance(pack, MeldPack) else pack
                if kind == "ANGANG":
                    kind = "GANG"
                tile_to_index(tile)
                if kind not in ("CHI", "PENG", "GANG") or not _int_range(offer, 0 if kind == "GANG" else 1, 3):
                    raise ValueError("Invalid meld type or offer")
                if kind == "CHI" and (tile[0] not in "WTB" or not 2 <= int(tile[1]) <= 8):
                    raise ValueError("Invalid Chi middle")
                result.append((kind, tile, int(offer)))
            except (ValueError, TypeError, IllegalActionError) as exc:
                raise EngineInvariantError(f"Invalid scoring pack: {pack!r}") from exc
        if len(result) > 4:
            raise EngineInvariantError("At most four melds are allowed")
        return tuple(result)

    @staticmethod
    def _validate_tiles(packs, hand_tiles, win_tile=None):
        try:
            for tile in hand_tiles:
                tile_to_index(tile)
            if win_tile is not None:
                tile_to_index(win_tile)
        except IllegalActionError as exc:
            raise EngineInvariantError("Invalid tile passed to scoring") from exc
        if len(hand_tiles) != 13 - 3 * len(packs):
            raise EngineInvariantError("Scoring requires 13 - 3 * meld_count concealed tiles before winning tile")
        counts = Counter(hand_tiles)
        for kind, tile, offer in packs:
            counts.update(MeldPack(kind, tile, offer).tiles())
        if win_tile is not None:
            counts[win_tile] += 1
        if any(n > 4 for n in counts.values()):
            raise EngineInvariantError("More than four copies of a normal tile")

    @classmethod
    def try_evaluate_hu(cls, packs, hand_tiles, win_tile, is_zimo, is_fourth_tile, is_about_kong, is_wall_last, seat_wind, prevalent_wind, flower_count=0) -> tuple[bool, int, tuple[FanItem, ...]]:
        gb_packs = cls.normalize_packs_for_gb(packs)
        hand = tuple(hand_tiles)
        cls._validate_tiles(gb_packs, hand, win_tile)
        if not _int_range(seat_wind, 0, 3) or not _int_range(prevalent_wind, 0, 3) or not _int_range(flower_count, 0, 8):
            raise EngineInvariantError("Invalid wind or flower count")
        try:
            raw = MahjongFanCalculator(gb_packs, hand, win_tile, int(flower_count), bool(is_zimo), bool(is_fourth_tile), bool(is_about_kong), bool(is_wall_last), int(seat_wind), int(prevalent_wind), True)
        except TypeError as exc:
            if str(exc) == "ERROR_NOT_WIN":
                return False, 0, ()
            raise EngineInvariantError(f"PyMahjongGB rejected scoring state: {exc}") from exc
        fans = tuple(FanItem(int(p), int(n), zh, en) for p, n, zh, en in raw)
        total = sum(f.fan_points * f.count for f in fans)
        base = sum(f.fan_points * f.count for f in fans if f.fan_name_en != "Flower Tiles")
        return base >= MIN_MCR_FAN, total, fans

    @classmethod
    def calculate_shanten(cls, packs, hand_tiles) -> int:
        gb_packs = cls.normalize_packs_for_gb(packs)
        hand = tuple(hand_tiles)
        cls._validate_tiles(gb_packs, hand)
        try:
            # PyMahjongGB 1.4.0 already minimizes regular and all supported special hands.
            return int(MahjongShanten(gb_packs, hand))
        except TypeError as exc:
            raise EngineInvariantError(f"PyMahjongGB rejected shanten state: {exc}") from exc


def compute_mcr_score_deltas(ending: RoundEnding, winner_seat: int | None, discarder_seat: int | None, total_fan: int) -> tuple[int, int, int, int]:
    if ending == "draw":
        if winner_seat is not None or discarder_seat is not None or total_fan != 0:
            raise IllegalActionError("A drawn round has no winner, discarder or fan")
        return (0, 0, 0, 0)
    if not _int_range(winner_seat, 0, 3) or not _int_range(total_fan, 8, 10000):
        raise IllegalActionError("A win requires a valid seat and at least 8 fan")
    if ending == "zimo" and discarder_seat is None:
        return tuple(3 * (8 + total_fan) if s == winner_seat else -(8 + total_fan) for s in range(4))
    if ending == "ron" and _int_range(discarder_seat, 0, 3) and discarder_seat != winner_seat:
        return tuple(24 + total_fan if s == winner_seat else -(8 + total_fan) if s == discarder_seat else -8 for s in range(4))
    raise IllegalActionError("Invalid round ending/winner/discarder")
