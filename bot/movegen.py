"""Move generation and static move ordering for the bitboard engine.

A full move list is hopeless here: three stones on a board with fifty empty
cells is about 21.000 moves.  Away from the end of the game the generator
therefore keeps only the empty cells next to existing stones, ranks them, and
builds placements out of the best few.  Once the board is nearly full it falls
back to exhaustive generation so the finish is searched exactly.

Placements always use the maximum number of stones allowed.  Holding stones
back never avoids the catch-up rule (which looks at whether your largest group
grew, not at how many stones you played), so it only gives away material.
"""
from __future__ import annotations

from bot.core import Position

# Below this many empty cells, generate every legal move.
EXACT_EMPTY_LIMIT = 9

# Bonus for each pair of stones inside one placement that touch each other.
LINK_BONUS = 2.2

# Static value of a single empty cell, by what it is adjacent to.
OWN_NEIGHBOR_WEIGHT = 3.0
OPPONENT_NEIGHBOR_WEIGHT = 1.3
EMPTY_NEIGHBOR_WEIGHT = 0.5
OWN_LARGEST_BONUS = 4.0
OPPONENT_LARGEST_BONUS = 2.5
# Cell adjacent to two of our groups: playing it joins them.
CONNECT_OWN_BONUS = 3.8
# Cell adjacent to two of their groups: occupying it stops their merge.
CUT_OPPONENT_BONUS = 2.4

HISTORY_SCALE = 0.012
HISTORY_CAP = 5.0


def generate(position: Position, width: int, cap: int, history=None) -> list[tuple[int, ...]]:
    """Ordered candidate moves, best first, at most ``cap`` of them."""
    limit = position.max_move()
    if limit == 0:
        return []

    if position.empty_count <= EXACT_EMPTY_LIMIT:
        return position.legal_moves()

    geo = position.geo
    occupied = position.stones[0] | position.stones[1]
    if not occupied:
        cells = sorted(geo.opening_cells, key=lambda cell: -geo.center_bonus[cell])
        return [(cell,) for cell in cells]

    frontier = geo.grow(occupied) & position.empty
    if frontier.bit_count() < width:
        frontier |= geo.grow(frontier) & position.empty

    scored = _score_cells(position, frontier, history)
    scored.sort(reverse=True)
    del scored[width:]
    scored.sort(key=_by_cell)
    cells = [cell for _, cell in scored]
    values = [value for value, _ in scored]

    moves = _combine(geo, cells, values, limit)
    moves.sort(reverse=True)
    if len(moves) > cap:
        del moves[cap:]
    return [move for _, move in moves]


def _by_cell(item):
    return item[1]


def _multi_group_cells(geo, groups, empty: int) -> int:
    """Empty cells that touch at least two groups of the same colour."""
    if len(groups) < 2:
        return 0
    grow = geo.grow
    cover = 0
    overlap = 0
    for group in groups:
        halo = grow(group) & empty
        overlap |= cover & halo
        cover |= halo
    return overlap


def _score_cells(position: Position, frontier: int, history) -> list[tuple[float, int]]:
    geo = position.geo
    me = position.side
    mine = position.stones[me]
    theirs = position.stones[me ^ 1]
    neighbor_mask = geo.neighbor_mask
    cell_of = geo.cell_of
    center = geo.center_bonus
    degree = geo.degree
    my_halo = geo.grow(position.top[me])
    their_halo = geo.grow(position.top[me ^ 1])
    own_join = _multi_group_cells(geo, position.groups[me], position.empty)
    their_join = _multi_group_cells(geo, position.groups[me ^ 1], position.empty)

    # Empty neighbours are whatever is left of the cell's degree, so only two
    # of the three counts have to be measured.
    empty_weight = EMPTY_NEIGHBOR_WEIGHT
    own_weight = OWN_NEIGHBOR_WEIGHT - empty_weight
    opponent_weight = OPPONENT_NEIGHBOR_WEIGHT - empty_weight

    out = []
    append = out.append
    mask = frontier
    while mask:
        low = mask & -mask
        mask ^= low
        cell = cell_of[low.bit_length() - 1]
        halo = neighbor_mask[cell]
        value = (
            own_weight * (halo & mine).bit_count()
            + opponent_weight * (halo & theirs).bit_count()
            + empty_weight * degree[cell]
            + center[cell]
        )
        if low & my_halo:
            value += OWN_LARGEST_BONUS
        if low & their_halo:
            value += OPPONENT_LARGEST_BONUS
        if low & own_join:
            value += CONNECT_OWN_BONUS
        if low & their_join:
            value += CUT_OPPONENT_BONUS
        if history is not None:
            bonus = HISTORY_SCALE * history[cell]
            value += bonus if bonus < HISTORY_CAP else HISTORY_CAP
        append((value, cell))
    return out


def _combine(geo, cells, values, limit):
    """All placements of ``limit`` stones over ``cells``, scored."""
    count = len(cells)
    if limit > count:
        limit = count

    if limit == 1:
        return [(values[i], (cells[i],)) for i in range(count)]

    bit = geo.bit
    neighbor_mask = geo.neighbor_mask
    adjacency = []
    for i in range(count):
        halo = neighbor_mask[cells[i]]
        mask = 0
        for j in range(i + 1, count):
            if halo & bit[cells[j]]:
                mask |= 1 << j
        adjacency.append(mask)

    moves = []
    append = moves.append
    if limit == 2:
        for i in range(count):
            near_i = adjacency[i]
            base = values[i]
            cell_i = cells[i]
            for j in range(i + 1, count):
                value = base + values[j]
                if near_i >> j & 1:
                    value += LINK_BONUS
                append((value, (cell_i, cells[j])))
        return moves

    for i in range(count):
        near_i = adjacency[i]
        base_i = values[i]
        cell_i = cells[i]
        for j in range(i + 1, count):
            base_j = base_i + values[j]
            if near_i >> j & 1:
                base_j += LINK_BONUS
            near_j = adjacency[j]
            cell_j = cells[j]
            for k in range(j + 1, count):
                value = base_j + values[k]
                if near_i >> k & 1:
                    value += LINK_BONUS
                if near_j >> k & 1:
                    value += LINK_BONUS
                append((value, (cell_i, cell_j, cells[k])))
    return moves
