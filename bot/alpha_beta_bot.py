from src.game import Game
from src.board import Cell,Board
from bot.evaluation import evaluate_v2
from time import perf_counter
import time
deadline = perf_counter() + 10.0
transposition_table = {}
################################# FOR BENCHMARK ####################
from dataclasses import dataclass
from math import isfinite

EPS = 0.25


@dataclass
class SearchStats:
    nodes: int = 0

    tt_probes: int = 0
    tt_hits: int = 0

    tt_exact_returns: int = 0
    tt_bound_cutoffs: int = 0

    alpha_beta_cutoffs: int = 0
    root_moves_completed: int = 0
    root_moves_total: int = 0
    lmr_reductions: int = 0
    lmr_researches: int = 0
    pvs_scout_searches: int = 0
    pvs_researches: int = 0
    EPS = 0.25
################################# FOR BENCHMARK####################
class SearchTimeout (Exception):
    pass
def check_timeout(deadline: float) -> None:
    if perf_counter() >= deadline:
        raise SearchTimeout()
def opponent_of(color:Cell) -> Cell:
    if color == Cell.WHITE:
        return Cell.BLACK
    return Cell.WHITE
def cheap_move_score(game:Game, move:list[tuple[int,int,int]], player:Cell) -> float:
    opponent = opponent_of(player)
    own_neighbors = 0
    opponent_neighbors = 0
    internal_connections = 0
    move_set = set(move)
    for position in move:
        for i in game.board.neighbors(position):
            if i in move_set:
                internal_connections +=1
                continue
            cell = game.board.get(i)
            if cell == player:
                own_neighbors +=1
            elif cell == opponent:
                opponent_neighbors +=1
    internal_connections //=2
    return (2.0* own_neighbors +1.0 *opponent_neighbors +2.0*internal_connections)
def state(game:Game):   #transposition table
    trangthai = list(game.board.cells.items())
    trangthai.sort(key=lambda item:item[0])
    return (tuple(trangthai),game.current_player, game.firstmove, game.increase_score)
def reduce_move (depth:int, move_index:int) -> bool:
    if depth <2:
        return False
    if move_index <20:
        return False
    return True
####################################################### ORDERING ##########################
def ordering (game:Game,bot_color:Cell, deadline:float =float( "inf"), prefer_move= None):
    ordering = []
    check_timeout(deadline)
    for move in game.possible_move():
        check_timeout(deadline)
        trial = game.copy()
        trial.play(move)
        ordering_score = evaluate_v2 (trial,bot_color)
        ordering.append ((move,trial, ordering_score))
    if game.current_player is bot_color:
        ordering.sort(key=lambda item:item[2],reverse=True)
    else:
        ordering.sort(key=lambda item:item[2],reverse=False)
    return ordering
def ordering_v2(game: Game, deadline:float=float("inf")):
    check_timeout(deadline)
    player = game.current_player
    moves = game.possible_move()
    scored_moves = []
    for i in moves:
        check_timeout(deadline)
        score = cheap_move_score(game, i, player)
        scored_moves.append((i,None, score))
    scored_moves.sort(
        key=lambda item: item[2],
        reverse=True
    )
    check_timeout(deadline)
    return scored_moves
####################################################### ALPHA-BETA ##########################
def alpha_beta(game:Game, depth:int, bot_color:Cell, alpha: float, beta: float,transposition_table , deadline:float=float("inf"),stats: SearchStats | None = None) -> float:
    check_timeout(deadline)
    if stats != None:
        stats.nodes += 1
    current_state = state(game)
    trangthai = (current_state, bot_color)
    ####################
    if stats != None:
        stats.tt_probes += 1

    tt_entry = transposition_table.get(trangthai)

    if tt_entry is not None:
        if stats != None:
            stats.tt_hits += 1  
    tt_entry = transposition_table.get(trangthai)
    ####################
    tt_best_move = None
    if tt_entry != None:
        tt_best_move = tt_entry["best_move"]
        if tt_entry["depth"] >= depth:
            value = tt_entry["value"]
            flag = tt_entry["flag"]
            if flag == "EXACT":
                if stats is not None:
                    stats.tt_exact_returns += 1
                return value
            elif flag == "LOWERBOUND":
                alpha = max(alpha,value)
            elif flag == "UPPERBOUND":
                beta = min(beta,value)
            if alpha >= beta: 
                if stats is not None:
                    stats.tt_bound_cutoffs += 1
                return value
    if game.game_over() or depth == 0:
        value = evaluate_v2(game, bot_color)
        old_entry = transposition_table.get(trangthai)
        if old_entry == None or depth>= old_entry["depth"]:   
            transposition_table[trangthai] = {"value": value,"depth": depth,"flag": "EXACT","best_move": None}
        return value
    #moves = game.possible_move()
    alpha_start = alpha
    beta_start = beta
    moves = ordering_v2(game,deadline)
    if tt_best_move != None:
        for i in range(len(moves)):
            check_timeout(deadline)
            if moves[i][0] == tt_best_move:
                preferred = moves.pop(i)
                moves.insert(0, preferred)
                break
    best_move = None
    #MAX
    if game.current_player == bot_color:
        best_value = float("-inf")
        for move_index in range(len(moves)):
            move, trial, ordering_score = moves[move_index]
            check_timeout(deadline)
            if trial == None:
                trial = game.copy()
                trial.play(move)
            if reduce_move(depth, move_index):
                if stats is not None:
                    stats.lmr_reductions += 1
                value = alpha_beta(trial, depth -2, bot_color,alpha,beta,transposition_table,deadline,stats)
                if value > alpha:
                    if stats != None:
                        stats.lmr_researches +=1
                    value = alpha_beta(trial, depth -1, bot_color,alpha,beta,transposition_table,deadline,stats)
            else:    
                value = alpha_beta(trial, depth -1, bot_color,alpha,beta,transposition_table,deadline,stats)
            if best_move ==  None or value > best_value:
                best_value = value
                best_move = move
            if best_value > alpha:
                alpha = best_value
            if alpha >=beta:
                if stats is not None:
                    stats.alpha_beta_cutoffs += 1
                break
        if best_value <= alpha_start:
            flag = "UPPERBOUND"
        elif best_value >= beta_start:
            flag = "LOWERBOUND"
        else:
            flag = "EXACT"
    #MIN
    else:
        best_value = float("inf")
        for move_index in range(len(moves)):
            move, trial, ordering_score = moves[move_index]            
            check_timeout(deadline)
            if trial == None:
                trial = game.copy()
                trial.play(move)
            if reduce_move(depth, move_index):
                if stats != None:
                    stats.lmr_reductions +=1
                value = alpha_beta(trial, depth -2, bot_color,alpha,beta,transposition_table,deadline,stats)
                if value <beta:
                    if stats != None:
                        stats.lmr_researches +=1
                    value = alpha_beta(trial, depth -1, bot_color,alpha,beta,transposition_table,deadline,stats)
            else:    
                value = alpha_beta(trial, depth -1, bot_color,alpha,beta,transposition_table,deadline,stats)
            if best_move == None or value < best_value:
                best_value = value
                best_move = move
            if best_value < beta:
                beta = best_value
            if alpha >= beta:
                if stats is not None:
                    stats.alpha_beta_cutoffs += 1
                break

        if best_value <= alpha_start:
            flag = "UPPERBOUND"
        elif best_value >= beta_start:
            flag = "LOWERBOUND"
        else:
            flag = "EXACT"
    old_entry = transposition_table.get(trangthai)
    if old_entry == None or depth >= old_entry["depth"]:
        transposition_table[trangthai] = {
            "value": best_value,
            "depth": depth,
            "flag": flag,
            "best_move": best_move.copy() if best_move != None else None
        }

    return best_value

def alpha_beta_move (game:Game, depth:int, transposition_table, deadline:float=float("inf"), prefer_move = None,stats: SearchStats | None = None) -> list[tuple[int,int,int]]:
    if game.game_over():
        return []
    check_timeout(deadline)
    bot_color = game.current_player
    best_move = None
    best_value = float ("-inf")

    alpha = float("-inf")
    beta = float ("inf")
    if depth > 1:
        moves = ordering_v2(game,deadline)
        if prefer_move != None:
            for i in range(len(moves)):
                check_timeout(deadline)
                entry = moves[i]
                if entry[0] == prefer_move:
                    prefer_entry = moves.pop(i)
                    moves.insert(0,prefer_entry)
                    break
        if stats is not None:
            stats.root_moves_completed = 0
            stats.root_moves_total = len(moves)
    else:
        moves = (
            (move, None, None)
            for move in game.possible_move()
        )
        if stats is not None:
            stats.root_moves_completed = 0
            stats.root_moves_total = 0

    for move,trial, ordering_score in moves:
        check_timeout(deadline)
        if trial == None:
            trial = game.copy()
            trial.play(move)
        value = alpha_beta (trial, depth - 1,bot_color,alpha,beta,transposition_table,deadline,stats)
        if stats != None:
            stats.root_moves_completed += 1
        if best_move == None or value > best_value:
            best_move = move
            best_value = value
        if best_value > alpha:
            alpha = best_value
    trangthai = (state(game), bot_color)
    old_entry = transposition_table.get(trangthai)
    if old_entry == None or depth >= old_entry["depth"]:
        transposition_table[trangthai] = {
            "value": best_value,
            "depth": depth,
            "flag": "EXACT",
            "best_move": best_move
        }
    return best_move

def iterative_move(game,time_limit: float) -> list[tuple[int,int,int]]:
    transposition_table = {}
    stats = SearchStats()
    if game.game_over():
        return[]
    deadline = perf_counter() + time_limit
    empty_positions = [position
                       for position, cell in game.board.cells.items()
                       if cell == Cell.EMPTY]
    best_move = [empty_positions[0]]
    prefer_move = None
    completed_depth = 0
    depth = 1
    ############
    search_start = perf_counter()
    print ()
    print("=" * 65)
    print("ITERATIVE DEEPENING")
    print("=" * 65)
    ###########
    while True:
        ##############
        iteration_start = perf_counter()
        nodes_before = stats.nodes
        tt_hits_before = stats.tt_hits
        tt_exact_before = stats.tt_exact_returns
        tt_bound_before = stats.tt_bound_cutoffs
        ab_cutoffs_before = stats.alpha_beta_cutoffs
        ##############
        try:
            check_timeout(deadline)
            candidate = alpha_beta_move(game,depth,transposition_table,deadline,prefer_move=prefer_move,stats=stats)
            check_timeout(deadline)
        except SearchTimeout:
            ##############
            iteration_time = (perf_counter() - iteration_start)
            iteration_nodes = (stats.nodes - nodes_before)
            print()
            print(f"Depth {depth}: TIMEOUT")
            print(
                f"  Time               : "
                f"{iteration_time:.3f}s"
            )
            print(
                f"  Partial nodes      : "
                f"{iteration_nodes}"
            )
            print(
                f"  TT hits            : "
                f"{stats.tt_hits - tt_hits_before}"
            )
            print(
                f"  TT exact returns   : "
                f"{stats.tt_exact_returns - tt_exact_before}"
            )
            print(
                f"  TT bound cutoffs   : "
                f"{stats.tt_bound_cutoffs - tt_bound_before}"
            )
            print(
                f"  Alpha-beta cutoffs : "
                f"{stats.alpha_beta_cutoffs - ab_cutoffs_before}"
            )
            print(
                f"  Root moves         : "
                f"{stats.root_moves_completed}/{stats.root_moves_total}"
            )
            ################
            break
        ############
        iteration_time = (
            perf_counter() - iteration_start
        )

        iteration_nodes = (
            stats.nodes - nodes_before
        )
        ############
        best_move =candidate
        prefer_move = candidate
        completed_depth = depth
        ############
        print()
        print(f"Depth {depth}: COMPLETED")
        print(
            f"  Time               : "
            f"{iteration_time:.3f}s"
        )
        print(
            f"  Nodes              : "
            f"{iteration_nodes}"
        )
        print(
            f"  TT hits            : "
            f"{stats.tt_hits - tt_hits_before}"
        )
        print(
            f"  TT exact returns   : "
            f"{stats.tt_exact_returns - tt_exact_before}"
        )
        print(
            f"  TT bound cutoffs   : "
            f"{stats.tt_bound_cutoffs - tt_bound_before}"
        )
        print(
            f"  Alpha-beta cutoffs : "
            f"{stats.alpha_beta_cutoffs - ab_cutoffs_before}"
        )
        print(
            f"  Best move          : "
            f"{best_move}"
        )
        ##############
        if depth >= len(empty_positions):
            break
        depth +=1
    ###################
    total_time = perf_counter() - search_start
    print()
    print("=" * 65)
    print("SEARCH SUMMARY")
    print("=" * 65)
    print(f"LMR reductions       : {stats.lmr_reductions}")
    print(f"LMR re-searches      : {stats.lmr_researches}")

    print(
        f"Time budget          : "
        f"{time_limit:.1f}s"
    )
    print(
        f"Actual time          : "
        f"{total_time:.3f}s"
    )
    print(
        f"Completed depth      : "
        f"{completed_depth}"
    )
    print(
        f"Total nodes          : "
        f"{stats.nodes}"
    )
    print(
        f"TT probes            : "
        f"{stats.tt_probes}"
    )
    print(
        f"TT hits              : "
        f"{stats.tt_hits}"
    )
    print(
        f"TT exact returns     : "
        f"{stats.tt_exact_returns}"
    )
    print(
        f"TT bound cutoffs     : "
        f"{stats.tt_bound_cutoffs}"
    )
    print(
        f"Alpha-beta cutoffs   : "
        f"{stats.alpha_beta_cutoffs}"
    )
    print(
        f"TT entries           : "
        f"{len(transposition_table)}"
    )
    print(
        f"Selected move        : "
        f"{best_move}"
    )
    #######################
    return best_move
