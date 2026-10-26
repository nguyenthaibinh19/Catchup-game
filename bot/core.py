"""Bitboard core for Catchup.

Cells live in a padded square grid so the six hexagonal directions become
constant bit shifts.  A position keeps one bitmask per colour, one bitmask per
connected group, and a Zobrist hash, all updated incrementally by make/unmake.
Nothing is copied during search.

The semantics mirror ``src.game.Game`` exactly: same cell set, same placement
limits (1 on the opening move, 2 normally, 3 when the previous mover grew their
score and the side to move is not ahead), and same lexicographic win condition.
"""
from __future__ import annotations

import random
from itertools import combinations

from src.board import Cell

WHITE = 0
BLACK = 1

COLOR_OF = (Cell.WHITE, Cell.BLACK)
SIDE_OF = {Cell.WHITE: WHITE, Cell.BLACK: BLACK}

CUBE_DIRECTIONS = (
    (1, -1, 0),
    (1, 0, -1),
    (0, 1, -1),
    (-1, 1, 0),
    (-1, 0, 1),
    (0, -1, 1),
)


def _rotate(position):
    x, y, z = position
    return (-z, -x, -y)


def _reflect(position):
    x, y, z = position
    return (x, z, y)


class Geometry:
    """Immutable per-radius lookup tables shared by every position."""

    __slots__ = (
        "radius", "width", "coords", "cell_count", "index", "bit", "cell_of",
        "neighbor_mask", "neighbor_list", "degree", "board_mask", "zobrist",
        "z_side", "z_increase", "z_firstmove", "center_bonus", "opening_cells",
        "_shift_a", "_shift_b",
    )

    def __init__(self, radius: int):
        self.radius = radius
        # One padding column and row on each side keeps the +-1 shifts from
        # wrapping a row into its neighbour.
        self.width = 2 * radius + 3
        coords = []
        for x in range(-radius, radius + 1):
            for y in range(-radius, radius + 1):
                if abs(x + y) <= radius:
                    coords.append((x, y, -x - y))
        self.coords = tuple(coords)
        self.cell_count = len(coords)
        self.index = {position: i for i, position in enumerate(coords)}

        offset = radius + 1
        self.bit = tuple(
            1 << ((x + offset) + self.width * (y + offset)) for x, y, _ in coords
        )
        board = 0
        for value in self.bit:
            board |= value
        self.board_mask = board

        self.cell_of = [0] * (self.width * self.width)
        for i, value in enumerate(self.bit):
            self.cell_of[value.bit_length() - 1] = i

        neighbor_mask = []
        neighbor_list = []
        for x, y, z in coords:
            mask = 0
            adjacent = []
            for dx, dy, dz in CUBE_DIRECTIONS:
                j = self.index.get((x + dx, y + dy, z + dz))
                if j is not None:
                    mask |= self.bit[j]
                    adjacent.append(j)
            neighbor_mask.append(mask)
            neighbor_list.append(tuple(adjacent))
        self.neighbor_mask = tuple(neighbor_mask)
        self.neighbor_list = tuple(neighbor_list)
        self.degree = tuple(len(adjacent) for adjacent in neighbor_list)

        self._shift_a = self.width - 1
        self._shift_b = self.width

        rng = random.Random(0xCA7C_0000 + radius)
        self.zobrist = (
            tuple(rng.getrandbits(64) for _ in coords),
            tuple(rng.getrandbits(64) for _ in coords),
        )
        self.z_side = rng.getrandbits(64)
        self.z_increase = rng.getrandbits(64)
        self.z_firstmove = rng.getrandbits(64)

        self.center_bonus = tuple(
            0.30 * (radius - max(abs(x), abs(y), abs(z))) / max(radius, 1)
            for x, y, z in coords
        )
        self.opening_cells = self._symmetry_unique_cells()

    def grow(self, mask: int) -> int:
        """Mask plus every on-board cell adjacent to it."""
        a = self._shift_a
        b = self._shift_b
        return (
            mask
            | mask << 1 | mask >> 1
            | mask << a | mask >> a
            | mask << b | mask >> b
        ) & self.board_mask

    def flood(self, seed: int, region: int) -> int:
        """Cells of ``region`` reachable from ``seed`` (``seed`` must be inside)."""
        a = self._shift_a
        b = self._shift_b
        board = self.board_mask
        current = seed
        while True:
            nxt = (
                current
                | current << 1 | current >> 1
                | current << a | current >> a
                | current << b | current >> b
            ) & board & region
            if nxt == current:
                return current
            current = nxt

    def cells_in(self, mask: int) -> list[int]:
        cell_of = self.cell_of
        out = []
        while mask:
            low = mask & -mask
            out.append(cell_of[low.bit_length() - 1])
            mask ^= low
        return out

    def _symmetry_unique_cells(self) -> tuple[int, ...]:
        transforms = []
        current = lambda position: position
        base = current
        for _ in range(6):
            transforms.append(base)
            transforms.append(lambda p, f=base: _reflect(f(p)))
            base = (lambda f: lambda p: _rotate(f(p)))(base)
        seen = set()
        unique = []
        for i, position in enumerate(self.coords):
            if position in seen:
                continue
            unique.append(i)
            for transform in transforms:
                seen.add(transform(position))
        return tuple(unique)


_GEOMETRIES: dict[int, Geometry] = {}


def geometry(radius: int) -> Geometry:
    geo = _GEOMETRIES.get(radius)
    if geo is None:
        geo = Geometry(radius)
        _GEOMETRIES[radius] = geo
    return geo


class Position:
    """Mutable Catchup position with incremental groups and hashing."""

    __slots__ = (
        "geo", "stones", "empty", "groups", "sizes", "best", "top", "side",
        "firstmove", "increase", "stone_hash", "empty_count", "_undo",
    )

    def __init__(self, geo: Geometry):
        self.geo = geo
        self.stones = [0, 0]
        self.empty = geo.board_mask
        self.groups = [[], []]
        self.sizes = [[], []]
        self.best = [0, 0]
        self.top = [0, 0]
        self.side = WHITE
        self.firstmove = True
        self.increase = False
        self.stone_hash = 0
        self.empty_count = geo.cell_count
        self._undo = []

    # ---------------------------------------------------------------- state

    def key(self) -> int:
        value = self.stone_hash
        geo = self.geo
        if self.side:
            value ^= geo.z_side
        if self.increase:
            value ^= geo.z_increase
        if self.firstmove:
            value ^= geo.z_firstmove
        return value

    def score(self, side: int) -> int:
        """Largest group size, or 1 when the colour has no stones (as in Board)."""
        return self.best[side] or 1

    def max_move(self) -> int:
        if self.empty_count == 0:
            return 0
        if self.firstmove:
            limit = 1
        elif self.increase and self.score(self.side ^ 1) >= self.score(self.side):
            limit = 3
        else:
            limit = 2
        return limit if limit <= self.empty_count else self.empty_count

    def result(self) -> int:
        """1 if White wins the current group vectors, -1 if Black, 0 if equal."""
        white = sorted(self.sizes[WHITE], reverse=True)
        black = sorted(self.sizes[BLACK], reverse=True)
        for i in range(max(len(white), len(black))):
            a = white[i] if i < len(white) else 0
            b = black[i] if i < len(black) else 0
            if a != b:
                return 1 if a > b else -1
        return 0

    def largest_group(self, side: int) -> int:
        return self.top[side]

    # ----------------------------------------------------------- make/unmake

    def make(self, cells) -> None:
        side = self.side
        geo = self.geo
        bit = geo.bit
        self._undo.append((
            self.groups[side], self.sizes[side], self.best[side], self.top[side],
            self.stones[side], self.empty, self.stone_hash,
            self.firstmove, self.increase, self.empty_count,
        ))
        before = self.best[side] or 1

        placed = 0
        value = self.stone_hash
        table = geo.zobrist[side]
        for cell in cells:
            placed |= bit[cell]
            value ^= table[cell]
        self.stones[side] |= placed
        self.empty &= ~placed
        self.stone_hash = value
        self.empty_count -= len(cells)

        self._merge(side, cells)

        self.increase = (self.best[side] or 1) > before
        self.firstmove = False
        self.side = side ^ 1

    def make_null(self) -> None:
        """Pass without placing.  Used only as a null-move pruning probe."""
        side = self.side
        self._undo.append((
            self.groups[side], self.sizes[side], self.best[side], self.top[side],
            self.stones[side], self.empty, self.stone_hash,
            self.firstmove, self.increase, self.empty_count,
        ))
        self.increase = False
        self.firstmove = False
        self.side = side ^ 1

    def unmake(self) -> None:
        side = self.side ^ 1
        (groups, sizes, best, top, stones, empty, stone_hash,
         firstmove, increase, empty_count) = self._undo.pop()
        self.side = side
        self.groups[side] = groups
        self.sizes[side] = sizes
        self.best[side] = best
        self.top[side] = top
        self.stones[side] = stones
        self.empty = empty
        self.stone_hash = stone_hash
        self.firstmove = firstmove
        self.increase = increase
        self.empty_count = empty_count

    def _merge(self, side: int, cells) -> None:
        """Rebuild the group list after ``cells`` joined ``side``'s stones.

        Each placed cell starts as its own blob.  Blobs that touch each other
        are fused first, then every old group is attached to the blob (if any)
        that reaches it.  An old group can bridge two blobs, which is why the
        scan keeps the first blob it hits and folds the others into it.

        An old group never needs its own halo here: two old groups that touch
        would already have been one group before this move.
        """
        bit = self.geo.bit
        neighbor_mask = self.geo.neighbor_mask
        old_groups = self.groups[side]
        old_sizes = self.sizes[side]

        count = len(cells)
        masks = [bit[cell] for cell in cells]
        halos = [neighbor_mask[cell] for cell in cells]
        blob_sizes = [1] * count
        alive = [True] * count

        for i in range(count):
            if not alive[i]:
                continue
            halo = halos[i]
            mask = masks[i]
            size = 1
            for j in range(i + 1, count):
                if alive[j] and halo & masks[j]:
                    mask |= masks[j]
                    halo |= halos[j]
                    size += 1
                    alive[j] = False
            masks[i] = mask
            halos[i] = halo
            blob_sizes[i] = size

        groups = []
        sizes = []
        for index, group in enumerate(old_groups):
            host = -1
            for i in range(count):
                if not alive[i] or not halos[i] & group:
                    continue
                if host < 0:
                    host = i
                else:
                    masks[host] |= masks[i]
                    halos[host] |= halos[i]
                    blob_sizes[host] += blob_sizes[i]
                    alive[i] = False
            if host < 0:
                groups.append(group)
                sizes.append(old_sizes[index])
            else:
                masks[host] |= group
                blob_sizes[host] += old_sizes[index]
        for i in range(count):
            if alive[i]:
                groups.append(masks[i])
                sizes.append(blob_sizes[i])

        self.groups[side] = groups
        self.sizes[side] = sizes
        largest = 0
        top = 0
        for i, size in enumerate(sizes):
            if size > largest:
                largest = size
                top = groups[i]
        self.best[side] = largest
        self.top[side] = top

    # --------------------------------------------------------------- loading

    def rebuild_groups(self, side: int) -> None:
        geo = self.geo
        remaining = self.stones[side]
        groups = []
        sizes = []
        while remaining:
            seed = remaining & -remaining
            component = geo.flood(seed, remaining)
            groups.append(component)
            sizes.append(component.bit_count())
            remaining ^= component
        self.groups[side] = groups
        self.sizes[side] = sizes
        largest = 0
        top = 0
        for i, size in enumerate(sizes):
            if size > largest:
                largest = size
                top = groups[i]
        self.best[side] = largest
        self.top[side] = top

    # ----------------------------------------------------------- legal moves

    def legal_moves(self) -> list[tuple[int, ...]]:
        """Every legal move, matching ``Game.possible_move`` as a set."""
        limit = self.max_move()
        if limit == 0:
            return []
        cells = self.geo.cells_in(self.empty)
        moves = []
        for size in range(1, limit + 1):
            moves.extend(combinations(cells, size))
        return moves

    def is_legal(self, cells) -> bool:
        if not cells or len(cells) > self.max_move():
            return False
        if len(set(cells)) != len(cells):
            return False
        bit = self.geo.bit
        empty = self.empty
        return all(bit[cell] & empty for cell in cells)


def position_from_game(game) -> Position:
    """Snapshot a ``src.game.Game`` into a search position."""
    geo = geometry(game.board.radius)
    position = Position(geo)
    index = geo.index
    bit = geo.bit
    white = 0
    black = 0
    for coord, cell in game.board.cells.items():
        if cell is Cell.EMPTY:
            continue
        value = bit[index[coord]]
        if cell is Cell.WHITE:
            white |= value
        else:
            black |= value
    position.stones = [white, black]
    occupied = white | black
    position.empty = geo.board_mask & ~occupied
    position.empty_count = geo.cell_count - occupied.bit_count()
    position.side = SIDE_OF[game.current_player]
    position.firstmove = game.firstmove
    position.increase = game.increase_score
    position.rebuild_groups(WHITE)
    position.rebuild_groups(BLACK)
    value = 0
    for side, mask in ((WHITE, white), (BLACK, black)):
        table = geo.zobrist[side]
        for cell in geo.cells_in(mask):
            value ^= table[cell]
    position.stone_hash = value
    return position


def move_to_coords(geo: Geometry, cells) -> list[tuple[int, int, int]]:
    return [geo.coords[cell] for cell in cells]
