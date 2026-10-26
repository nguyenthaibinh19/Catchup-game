from src.board import Cell
from src.game import Game
from bot.evaluation import evaluate

def optimize_move (game:Game) -> list[tuple[int,int,int]]:
    if game.game_over():
        return []
    bot_color = game.current_player
    moves = game.possible_move()
    best_move = None
    best_value = float ("-inf")
    for move in moves:
        trial = game.copy()
        trial.play(move)
        value = evaluate(trial,bot_color)
        if best_move == None or value > best_value:
            best_move = move
            best_value = value
    return best_move