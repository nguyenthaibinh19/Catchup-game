from itertools import count, combinations
from src.board import Board, Cell
from copy import copy as cp
from math import comb
from typing import Iterator
class Game:
    def __init__(self, radius):
        self.board = Board(radius)
        self.current_player = Cell.WHITE
        self.firstmove = True
        self.increase_score = False

    def max_move(self) -> int:
        empty_count = 0
        for cell in self.board.cells.values():
            if cell == Cell.EMPTY:
                empty_count += 1
        if empty_count == 0:
            return 0
        if self.firstmove:
            limit = 1

        else:
            if self.current_player == Cell.WHITE:
                opponent = Cell.BLACK
            else:
                opponent = Cell.WHITE
            current_score = self.board.score(self.current_player)
            opponent_score = self.board.score(opponent)
            if self.increase_score == True and opponent_score >= current_score:
                limit = 3
            else:
                limit = 2
        if limit > empty_count:
            return empty_count
        else:
            return limit

    def play(self, position: list[tuple[int, int, int]]) -> None:
        limit = self.max_move()
        if limit == 0:
            raise Exception("No moves left")
        if len(position) == 0:
            raise Exception("Must select at least one cell")
        if len(position) > limit:
            raise Exception(f"Cannot select more than {limit} cells")
        checked = []
        for i in position:
            if i in checked:
                raise Exception(f"You cannot select the same cell {i} twice")
            if i not in self.board.cells:
                raise Exception(f"Cell {i} is not on the board")
            if self.board.cells[i] != Cell.EMPTY:
                raise Exception(f"Cell {i} is not empty")
            checked.append(i)
        score_before = self.board.score(self.current_player)
        for selected_stone in position:
            self.board.place(selected_stone, self.current_player)
        score_after = self.board.score(self.current_player)
        if score_after > score_before:
            self.increase_score = True
        else:
            self.increase_score = False
        self.firstmove = False
        if self.current_player == Cell.WHITE:
            self.current_player = Cell.BLACK
        else:
            self.current_player = Cell.WHITE

    def game_over(self) -> bool:
        for cell in self.board.cells.values():
            if cell == Cell.EMPTY:
                return False
        return True

    def winner(self) -> Cell | None:
        white_scores = self.board.group_sizes(Cell.WHITE)
        black_scores = self.board.group_sizes(Cell.BLACK)
        compare_numbers = max(len(white_scores), len(black_scores))
        for i in range(compare_numbers):
            if i < len(white_scores):
                white_score = white_scores[i]
            else:   
                white_score = 0

            if i < len(black_scores):
                black_score = black_scores[i]
            else:
                black_score = 0

            if white_score > black_score:
                return Cell.WHITE
            elif black_score > white_score:
                return Cell.BLACK
        return None

    def copy(self) -> "Game":
        copy_game = cp(self)
        copy_game.board = cp(self.board)
        copy_game.board.cells = self.board.cells.copy()
        copy_game.current_player = self.current_player
        copy_game.firstmove = self.firstmove
        copy_game.increase_score = self.increase_score  
        copy_game.board.group_sizes_cache = {}
        for color,sizes in self.board.group_sizes_cache.items():
            if sizes == None:
                copy_game.board.group_sizes_cache[color] = None
            else:
                copy_game.board.group_sizes_cache[color] = sizes.copy()
        return copy_game

    def possible_move(self) -> list[list[tuple[int,int,int]]]:
        limit = self.max_move()
        empty_positions = [
            position 
            for position, cell in self.board.cells.items() 
            if cell == Cell.EMPTY]
        result = []
        limit = min(limit, len(empty_positions))

        for count in range(1, limit + 1):
            for move in combinations(empty_positions, count):
                result.append(list(move))
        return result

    def possible_move_iter(self) -> Iterator[list[tuple[int,int,int]]]:
        limit = self.max_move()
        empty_positions = [
            position 
            for position, cell in self.board.cells.items() 
            if cell == Cell.EMPTY]
        limit = min(limit, len(empty_positions))

        for count in range(1, limit + 1):
            for move in combinations(empty_positions, count):
                yield list(move)

    def possible_move_count(self) -> int:
        empty_count = 0
        for cell in self.board.cells.values():
            if cell == Cell.EMPTY:
                empty_count += 1
        limit = min(self.max_move(), empty_count)
        total = 0
        for i in range(1, limit + 1):
            total += comb(empty_count, i)
        return total