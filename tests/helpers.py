from app.domain.tiles import TILE_LIST


def make_wall(hands, draws=None, flowers=False):
    """Valid deterministic fixture: each seat consumes its own segment backwards."""
    from app.domain.tiles import FLOWER_TILES
    draws = draws or [[] for _ in range(4)]
    hands = [list(h) for h in hands]
    pool = [t for t in TILE_LIST for _ in range(4)] + (list(FLOWER_TILES) if flowers else [])
    for tiles in hands + draws:
        for tile in tiles:
            pool.remove(tile)
    # Fill unspecified starting hands only with normal tiles.
    for h in hands:
        while len(h) < 13:
            tile = next(t for t in pool if not t.startswith("H"))
            pool.remove(tile)
            h.append(tile)
    size = 36 if flowers else 34
    segments = []
    for seat in range(4):
        filler = [pool.pop() for _ in range(size - 13 - len(draws[seat]))]
        segments.extend(filler + list(reversed(draws[seat])) + list(reversed(hands[seat])))
    assert not pool
    return segments


def pass_claims(engine):
    if engine.phase in ("CLAIM_DISCARD", "CLAIM_QIANGGANG"):
        for seat in engine.get_pending_seats():
            engine.submit_seat_action(seat, 0)


def play_pass(engine, seat, tile):
    from app.domain.actions import encode_play_action
    engine.submit_seat_action(seat, encode_play_action(tile))
    pass_claims(engine)
