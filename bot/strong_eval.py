"""Evaluation for the bitboard Catchup engine.

Scores are returned from the point of view of the side to move, so the search
can stay in plain negamax form.

Catchup is won by comparing the sorted group-size vectors, and in practice by
the single largest group.  The leading term is therefore not the group sizes on
the board but a projection of how large each side's main group can still
become: the empty cells are split between the players by which side reaches
them first, and each side's largest group is then flooded through its own share
of the board.  That projection is what distinguishes a group that still has
room from one that is already walled in, and it is what punishes splitting into
two halves that the opponent can keep apart.
"""
from __future__ import annotations

from bot.core import Position

WIN = 1_000_000.0

# Projected final size of the main group, after splitting the empty cells by
# who reaches them first.
PROJECTION_WEIGHT = 0.50

# Weight of the largest group actually on the board, then of the tail of the
# sorted vector that decides tied games.
LARGEST_GROUP_WEIGHT = 1.0
TAIL_SCALE = 1.0
TAIL_WEIGHTS = (0.30, 0.11, 0.045, 0.02)

# Empty cells next to the largest group: room to grow right now.
LARGEST_LIBERTY_WEIGHT = 0.22
# Empty cells next to any stone: flexibility and blocking power.
TOTAL_LIBERTY_WEIGHT = 0.045
# Optimistic reach, ignoring the opponent.  Superseded by the projection and
# kept only so the two can be compared.
POTENTIAL_WEIGHT = 0.0
# Being the side that gets three stones is worth something on its own.
TEMPO_WEIGHT = 0.10
# Two of our groups share an empty neighbour: they can merge next move.
MERGE_THREAT_WEIGHT = 0.42
# Empty cells both sides would reach in the same ring.  Side to move takes them.
CONTESTED_WEIGHT = 0.06

_TAIL_COUNT = len(TAIL_WEIGHTS)


def terminal_score(position: Position, ply: int) -> float:
    """Exact score of a filled board, from the side to move's point of view."""
    outcome = position.result()
    if outcome == 0:
        return 0.0
    white_won = outcome > 0
    if white_won == (position.side == 0):
        return WIN - ply
    return -(WIN - ply)


def evaluate(position: Position) -> float:
    me = position.side
    opponent = me ^ 1

    mine = position.sizes[me]
    theirs = position.sizes[opponent]
    if len(mine) > 1:
        mine = sorted(mine, reverse=True)
    if len(theirs) > 1:
        theirs = sorted(theirs, reverse=True)
    value = LARGEST_GROUP_WEIGHT * (
        (mine[0] if mine else 0) - (theirs[0] if theirs else 0)
    )
    for i in range(_TAIL_COUNT):
        a = mine[i + 1] if i + 1 < len(mine) else 0
        b = theirs[i + 1] if i + 1 < len(theirs) else 0
        if a != b:
            value += TAIL_SCALE * TAIL_WEIGHTS[i] * (a - b)

    geo = position.geo
    grow = geo.grow
    empty = position.empty
    my_stones = position.stones[me]
    their_stones = position.stones[opponent]
    my_largest = position.top[me]
    their_largest = position.top[opponent]

    my_liberties = (grow(my_largest) & empty).bit_count() if my_largest else 0
    their_liberties = (grow(their_largest) & empty).bit_count() if their_largest else 0
    value += LARGEST_LIBERTY_WEIGHT * (my_liberties - their_liberties)

    my_room = (grow(my_stones) & empty).bit_count()
    their_room = (grow(their_stones) & empty).bit_count()
    value += TOTAL_LIBERTY_WEIGHT * (my_room - their_room)

    if PROJECTION_WEIGHT and my_stones and their_stones:
        my_share, their_share, contested = _split_empty(
            geo, my_stones, their_stones, empty
        )
        value += PROJECTION_WEIGHT * (
            _flood_size(geo, my_largest, my_stones | my_share)
            - _flood_size(geo, their_largest, their_stones | their_share)
        )
        if CONTESTED_WEIGHT and contested:
            value += CONTESTED_WEIGHT * contested.bit_count()

    if POTENTIAL_WEIGHT:
        value += POTENTIAL_WEIGHT * (
            _flood_size(geo, my_largest, my_stones | empty)
            - _flood_size(geo, their_largest, their_stones | empty)
        )

    if MERGE_THREAT_WEIGHT:
        value += MERGE_THREAT_WEIGHT * (
            _merge_gain(geo, position.groups[me], position.sizes[me],
                        empty, position.best[me])
            - _merge_gain(geo, position.groups[opponent], position.sizes[opponent],
                          empty, position.best[opponent])
        )

    value += TEMPO_WEIGHT * position.max_move()
    return value


def _split_empty(geo, mine: int, theirs: int, empty: int) -> tuple[int, int, int]:
    """Give each empty cell to the side whose stones reach it first.

    Both sides expand one ring per round; cells reached by both in the same
    round belong to nobody but still carry the frontier forward.
    """
    grow = geo.grow
    frontier_mine = mine
    frontier_theirs = theirs
    free = empty
    my_share = 0
    their_share = 0
    contested = 0
    while free:
        next_mine = grow(frontier_mine) & free if frontier_mine else 0
        next_theirs = grow(frontier_theirs) & free if frontier_theirs else 0
        if not next_mine and not next_theirs:
            break
        shared = next_mine & next_theirs
        contested |= shared
        my_share |= next_mine ^ shared
        their_share |= next_theirs ^ shared
        free &= ~(next_mine | next_theirs)
        frontier_mine = next_mine
        frontier_theirs = next_theirs
    return my_share, their_share, contested


def _merge_gain(geo, groups, sizes, empty: int, current_best: int) -> int:
    """Biggest size jump available by joining two groups through one empty cell."""
    count = len(groups)
    if count < 2:
        return 0
    grow = geo.grow
    liberties = [grow(group) & empty for group in groups]
    best = 0
    for i in range(count):
        shared_i = liberties[i]
        size_i = sizes[i]
        for j in range(i + 1, count):
            if shared_i & liberties[j]:
                gain = size_i + sizes[j] + 1 - current_best
                if gain > best:
                    best = gain
    return best


def _flood_size(geo, group: int, region: int) -> int:
    if not group:
        return 0
    return geo.flood(group, region).bit_count()
