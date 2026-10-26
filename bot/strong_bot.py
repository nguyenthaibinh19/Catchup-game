"""Negamax principal-variation search for Catchup.

Drop-in replacement for ``bot.pvs_bot``: ``iterative_move(game, time_limit)``
returns a legal move for ``game.current_player`` as a list of cube coordinates.

The search runs on ``bot.core.Position`` (bitboards, make/unmake, Zobrist) and
uses a transposition table, killer moves, a history heuristic, principal
variation search, late move reductions, null-move pruning, razoring,
internal iterative deepening and aspiration windows.  Candidate moves are
restricted to the area around existing stones until the board is nearly
full, which is what makes any useful depth reachable given the branching
factor.
"""
from __future__ import annotations

import sys
from time import perf_counter

from bot.core import Position, geometry, move_to_coords, position_from_game
from bot.movegen import generate
from bot.strong_eval import WIN, evaluate, terminal_score

INFINITY = float("inf")
NULL_WINDOW = 1e-4
ASPIRATION_WINDOW = 1.0
# Centre the window on the previous score of the same depth parity rather than
# on the previous depth.  Set to 0 to use the previous depth.
ASPIRATION_PARITY = 1.0

EXACT = 0
LOWERBOUND = 1
UPPERBOUND = 2

# How many candidate cells are ranked and how many placements are searched,
# as a function of the remaining depth.  Shallow nodes are the overwhelming
# majority, so they stay narrow; deep nodes can afford to look wider.
BASE_WIDTH = 6
WIDTH_STEP = 2
MAX_WIDTH = 14
BASE_CAP = 10
CAP_STEP = 6
MAX_CAP = 36
ROOT_WIDTH = 18
ROOT_CAP = 72

LMR_MIN_DEPTH = 3
LMR_FIRST_LATE_MOVE = 3

# Reverse futility / razoring / late-move futility.  Margins are in eval units
# (about one stone of largest-group difference).
RFP_MARGIN = 1.15
# 0 disables reverse-futility pruning.  A short gauntlet scored the bot
# stronger with this off: it was cutting lines whose eval sat inside the
# margin but that still reversed after a catch-up placement.
RFP_MAX_DEPTH = 0
RAZOR_MARGIN = 1.45
RAZOR_MAX_DEPTH = 2
FUTILITY_MARGIN = 2.2
# High enough that late-move futility never fires.  Skipping those moves
# dropped strength in a self-play gauntlet (catch-up bursts hide in the tail).
FUTILITY_FIRST_MOVE = 10_000
NMP_MIN_DEPTH = 3
NMP_REDUCTION = 2
IID_MIN_DEPTH = 5
# Speculative pruning is unsound once the remaining board is small enough to
# search exactly.
ENDGAME_EMPTY = 12

_PLAN_LENGTH = 72
_PLAN: list[tuple[int, int]] = []


def build_plan() -> None:
    """Refresh the per-depth generation limits after a parameter change."""
    _PLAN.clear()
    for depth in range(_PLAN_LENGTH):
        step = max(depth - 1, 0)
        _PLAN.append((
            int(min(BASE_WIDTH + WIDTH_STEP * step, MAX_WIDTH)),
            int(min(BASE_CAP + CAP_STEP * step, MAX_CAP)),
        ))


build_plan()

TT_LIMIT = 2_000_000

sys.setrecursionlimit(10_000)


class SearchTimeout(Exception):
    pass


class SearchStats:
    __slots__ = ("nodes", "tt_hits", "cutoffs", "researches", "depth", "score",
                 "elapsed")

    def __init__(self):
        self.nodes = 0
        self.tt_hits = 0
        self.cutoffs = 0
        self.researches = 0
        self.depth = 0
        self.score = 0.0
        self.elapsed = 0.0


class Searcher:
    """Holds the tables that are worth keeping between moves of one game."""

    def __init__(self, radius: int = 4):
        self.geo = geometry(radius)
        self.tt: dict[int, tuple] = {}
        self.history = [
            [0.0] * self.geo.cell_count,
            [0.0] * self.geo.cell_count,
        ]
        self.killers: list[list] = []
        self.deadline = 0.0
        self.stats = SearchStats()

    # ------------------------------------------------------------- plumbing

    def _ensure_killers(self, ply: int) -> None:
        while len(self.killers) <= ply:
            self.killers.append([None, None])

    def _age_history(self) -> None:
        for table in self.history:
            for i, value in enumerate(table):
                if value:
                    table[i] = value * 0.5

    def _store(self, key: int, depth: int, value: float, flag: int, move) -> None:
        tt = self.tt
        entry = tt.get(key)
        if entry is None:
            if len(tt) >= TT_LIMIT:
                return
        elif depth < entry[0]:
            return
        tt[key] = (depth, value, flag, move)

    def _order(self, position: Position, moves, tt_move, killers):
        head = []
        for candidate in (tt_move, killers[0], killers[1]):
            if candidate is None or candidate in head:
                continue
            if position.is_legal(candidate):
                head.append(candidate)
        if not head:
            return moves
        head.extend(move for move in moves if move not in head)
        return head

    def _remember(self, move, depth: int, ply: int, side: int) -> None:
        killers = self.killers[ply]
        if killers[0] != move:
            killers[1] = killers[0]
            killers[0] = move
        table = self.history[side]
        bonus = float(depth * depth)
        for cell in move:
            table[cell] += bonus

    # --------------------------------------------------------------- search

    def search(self, position: Position, depth: int, alpha: float, beta: float,
               ply: int, allow_iid: bool = True) -> float:
        stats = self.stats
        stats.nodes += 1
        if not stats.nodes & 511 and perf_counter() >= self.deadline:
            raise SearchTimeout

        if position.empty_count == 0:
            return terminal_score(position, ply)

        is_pv = beta - alpha > NULL_WINDOW + 1e-12
        in_endgame = position.empty_count <= ENDGAME_EMPTY
        key = position.key()
        entry = self.tt.get(key)
        tt_move = None
        if entry is not None:
            stored_depth, stored_value, flag, tt_move = entry
            if stored_depth >= depth:
                stats.tt_hits += 1
                if flag == EXACT:
                    return stored_value
                if flag == LOWERBOUND:
                    if stored_value > alpha:
                        alpha = stored_value
                elif stored_value < beta:
                    beta = stored_value
                if alpha >= beta:
                    return stored_value

        if depth <= 0:
            value = evaluate(position)
            self._store(key, 0, value, EXACT, tt_move)
            return value

        static = None
        if not is_pv and not in_endgame and ply > 0:
            if depth <= RFP_MAX_DEPTH:
                static = evaluate(position)
                if static - RFP_MARGIN * depth >= beta:
                    return static
            if depth <= RAZOR_MAX_DEPTH:
                if static is None:
                    static = evaluate(position)
                if static + RAZOR_MARGIN * depth <= alpha:
                    return static
            if (depth >= NMP_MIN_DEPTH
                    and position.stones[0] and position.stones[1]
                    and not position.firstmove
                    and position.max_move() < 3):
                reduction = NMP_REDUCTION + (1 if depth >= 6 else 0)
                if reduction > depth - 2:
                    reduction = depth - 2
                if reduction >= 1:
                    position.make_null()
                    try:
                        value = -self.search(
                            position, depth - 1 - reduction,
                            -beta, -beta + NULL_WINDOW, ply + 1,
                        )
                    finally:
                        position.unmake()
                    if value >= beta and abs(value) < WIN / 2:
                        return value

        if allow_iid and tt_move is None and is_pv and depth >= IID_MIN_DEPTH:
            self.search(position, depth - 2, alpha, beta, ply, allow_iid=False)
            entry = self.tt.get(key)
            if entry is not None:
                tt_move = entry[3]

        original_alpha = alpha
        width, cap = _PLAN[depth] if depth < _PLAN_LENGTH else _PLAN[-1]
        moves = generate(position, width, cap, self.history[position.side])
        if not moves:
            return evaluate(position)

        self._ensure_killers(ply)
        moves = self._order(position, moves, tt_move, self.killers[ply])

        best_value = -INFINITY
        best_move = None
        for index, move in enumerate(moves):
            if (not is_pv and not in_endgame and depth == 1
                    and index >= FUTILITY_FIRST_MOVE):
                if static is None:
                    static = evaluate(position)
                if static + FUTILITY_MARGIN <= alpha:
                    continue
            position.make(move)
            try:
                if index == 0:
                    value = -self.search(position, depth - 1, -beta, -alpha, ply + 1)
                else:
                    reduction = 0
                    if (depth >= LMR_MIN_DEPTH and index >= LMR_FIRST_LATE_MOVE
                            and not in_endgame):
                        reduction = 1 if index < 8 else 2
                        if is_pv:
                            reduction -= 1
                        if reduction > depth - 2:
                            reduction = depth - 2
                        if reduction < 0:
                            reduction = 0
                    value = -self.search(position, depth - 1 - reduction,
                                         -alpha - NULL_WINDOW, -alpha, ply + 1)
                    if reduction and value > alpha:
                        value = -self.search(position, depth - 1,
                                             -alpha - NULL_WINDOW, -alpha, ply + 1)
                    if alpha < value < beta:
                        stats.researches += 1
                        value = -self.search(position, depth - 1, -beta, -alpha,
                                             ply + 1)
            finally:
                position.unmake()

            if value > best_value:
                best_value = value
                best_move = move
                if value > alpha:
                    alpha = value
                    if alpha >= beta:
                        stats.cutoffs += 1
                        self._remember(move, depth, ply, position.side)
                        break

        if best_move is None:
            return static if static is not None else evaluate(position)

        if best_value <= original_alpha:
            flag = UPPERBOUND
        elif best_value >= beta:
            flag = LOWERBOUND
        else:
            flag = EXACT
        self._store(key, depth, best_value, flag, best_move)
        return best_value

    # ----------------------------------------------------------------- root

    def _root_order(self, position: Position, moves, preferred):
        scored = []
        for move in moves:
            position.make(move)
            try:
                scored.append((evaluate(position), move))
            finally:
                position.unmake()
        scored.sort(key=lambda item: item[0])
        ordered = [move for _, move in scored]
        if preferred is not None and preferred in ordered:
            ordered.remove(preferred)
            ordered.insert(0, preferred)
        return ordered

    def search_root(self, position: Position, depth: int, alpha: float,
                    beta: float, preferred):
        moves = generate(position, ROOT_WIDTH, ROOT_CAP, self.history[position.side])
        if not moves:
            return None, 0.0
        if preferred is not None and position.is_legal(preferred):
            if preferred not in moves:
                moves.append(preferred)
        moves = self._root_order(position, moves, preferred)

        best_value = -INFINITY
        best_move = None
        for index, move in enumerate(moves):
            position.make(move)
            try:
                if index == 0:
                    value = -self.search(position, depth - 1, -beta, -alpha, 1)
                else:
                    value = -self.search(position, depth - 1,
                                         -alpha - NULL_WINDOW, -alpha, 1)
                    if alpha < value < beta:
                        value = -self.search(position, depth - 1, -beta, -alpha, 1)
            finally:
                position.unmake()

            if value > best_value:
                best_value = value
                best_move = move
                if value > alpha:
                    alpha = value
                    if alpha >= beta:
                        break
        return best_move, best_value

    def _aspiration(self, position: Position, depth: int, score, preferred):
        if score is None:
            alpha, beta = -INFINITY, INFINITY
        else:
            alpha = score - ASPIRATION_WINDOW
            beta = score + ASPIRATION_WINDOW
        while True:
            move, value = self.search_root(position, depth, alpha, beta, preferred)
            if move is None:
                return None, 0.0
            if value <= alpha and alpha > -INFINITY:
                alpha = -INFINITY
                continue
            if value >= beta and beta < INFINITY:
                beta = INFINITY
                continue
            return move, value

    # ------------------------------------------------------------ top level

    def find_move(self, position: Position, time_limit: float, report=None):
        start = perf_counter()
        self.deadline = start + max(time_limit, 0.0) * 0.98
        self.stats = SearchStats()
        self.killers = []
        self._age_history()

        if position.max_move() == 0:
            return None
        candidates = generate(position, ROOT_WIDTH, ROOT_CAP,
                              self.history[position.side])
        if not candidates:
            return None

        best_move = candidates[0]
        base_undo = len(position._undo)
        # Scores alternate with the parity of the depth, because one more ply
        # means the other side placed last.  Centring the aspiration window on
        # the previous score of the same parity avoids a re-search per depth.
        by_parity: list[float | None] = [None, None]
        depth = 1
        max_depth = position.empty_count + 1

        while depth <= max_depth:
            iteration_start = perf_counter()
            if depth > 1 and iteration_start >= self.deadline:
                break
            try:
                centre = by_parity[depth & 1] if ASPIRATION_PARITY else by_parity[0]
                move, value = self._aspiration(position, depth, centre, best_move)
            except SearchTimeout:
                while len(position._undo) > base_undo:
                    position.unmake()
                break
            if move is None:
                break

            previous_score = by_parity[depth & 1]
            unstable = (
                move != best_move
                or (previous_score is not None and abs(value - previous_score) > 0.75)
            )
            best_move = move
            by_parity[depth & 1] = value
            if not ASPIRATION_PARITY:
                by_parity[0] = value
            self.stats.depth = depth
            self.stats.score = value
            iteration_time = perf_counter() - iteration_start
            if report is not None:
                report(depth, value, move, iteration_time, self.stats)

            if abs(value) > WIN / 2:
                break
            factor = 1.25 if unstable else 1.85
            if self.deadline - perf_counter() <= iteration_time * factor:
                break
            depth += 1

        self.stats.elapsed = perf_counter() - start
        return best_move


_SEARCHER: Searcher | None = None


def _searcher(radius: int) -> Searcher:
    global _SEARCHER
    if _SEARCHER is None or _SEARCHER.geo.radius != radius:
        _SEARCHER = Searcher(radius)
    return _SEARCHER


def iterative_move(game, time_limit: float = 15.0, verbose: bool = True) -> list:
    """Best move for ``game.current_player`` as a list of cube coordinates."""
    if game.game_over():
        return []
    searcher = _searcher(game.board.radius)
    position = position_from_game(game)

    def report(depth, value, move, seconds, stats):
        print(
            f"depth {depth:2d}  score {value:+9.2f}  {seconds:6.2f}s  "
            f"{stats.nodes:9d} nodes  {move_to_coords(searcher.geo, move)}",
            flush=True,
        )

    move = searcher.find_move(position, time_limit, report if verbose else None)
    if move is None:
        legal = position.legal_moves()
        if not legal:
            return []
        move = legal[0]
    if verbose:
        stats = searcher.stats
        rate = stats.nodes / stats.elapsed if stats.elapsed else 0.0
        print(
            f"-> depth {stats.depth}, {stats.nodes} nodes in {stats.elapsed:.2f}s "
            f"({rate:,.0f} n/s), tt {len(searcher.tt)}",
            flush=True,
        )
    return move_to_coords(searcher.geo, move)


def best_move(game, time_limit: float = 15.0) -> list:
    return iterative_move(game, time_limit, verbose=False)
