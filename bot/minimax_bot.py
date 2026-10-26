from src.game import Game
from src.board import Cell
from bot.evaluation import evaluate


def minimax(game: Game, depth: int, bot_color: Cell) -> float:
    if game.game_over() or depth == 0:
        return evaluate(game, bot_color)
    moves = game.possible_move()
    if game.current_player == bot_color:
        best_value =float ("-inf")
        for move in moves:
            trial = game.copy()
            trial.play(move)
            value = minimax (trial, depth - 1, bot_color)
            if value > best_value:
                best_value = value
        return best_value
    else:
        best_value = float ("inf")
        for move in moves:
            trial = game.copy()
            trial.play(move)
            value = minimax (trial, depth -1, bot_color)
            if value < best_value:
                best_value = value
        return best_value

def minimax_move (game: Game, depth: int) ->list[tuple[int,int,int]]:
    if game.game_over():
        return []
    bot_color = game.current_player
    moves = game.possible_move()
    best_move = None
    best_value = float("-inf")
    for move in moves:
        trial = game.copy()
        trial.play(move)
        value = minimax(trial, depth -1, bot_color)
        if best_move == None or best_value < value:
            best_move = move
            best_value = value
    return best_move