from src.game import Game
from src.board import Board, Cell
import random

def move_random(game: Game) -> list[tuple[int, int, int]]:
    task_limit = game.max_move()
    if task_limit == 0:
        return []
    empty_positions = [position for position, cell in game.board.cells.items() if cell == Cell.EMPTY]
    num_to_place = random.randint(1, task_limit)
    selected_positions = random.sample(empty_positions, num_to_place)
    return selected_positions