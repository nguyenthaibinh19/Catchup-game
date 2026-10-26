from enum import Enum
from tokenize import group

class Cell(Enum):
    EMPTY = 0
    WHITE = 1
    BLACK = 2

class Board:
    def __init__(self, radius: int):
        self.radius = radius
        self.size = 2 * radius + 1
        self.cells = {}
        self.group_sizes_cache = {Cell.WHITE: None, Cell.BLACK : None}
        for x in range(-radius, radius + 1):
            for y in range(-radius, radius + 1):
                z= -x-y
                if abs(x) <= radius and abs(y) <= radius and abs(z) <= radius:
                    self.cells[(x, y, z)] = Cell.EMPTY  
        self.neighbors_map = {}
        directions = (
            (1, -1, 0),
            (1, 0, -1),
            (0, 1, -1),
            (-1, 1, 0),
            (-1, 0, 1),
            (0, -1, 1),
        )
        for position in self.cells:
            x, y, z = position
            adjacent = []

            for dx, dy, dz in directions:
                candidate = (x + dx, y + dy, z + dz)

                if candidate in self.cells:
                    adjacent.append(candidate)

            self.neighbors_map[position] = tuple(adjacent)

    def contains(self, position: tuple[int, int, int]) -> bool:
        x, y, z = position
        if position in self.cells:
            return True
        else:
            return False

    def get (self, position: tuple[int, int, int]) -> Cell:
        if self.contains(position):
            return self.cells[position]
        else:
            raise ValueError("Position is out of bounds")

    def place(self,position: tuple[int, int, int],cell: Cell,) -> None:
        if not self.contains(position):
            raise ValueError("Position is out of bounds")
        if cell == Cell.EMPTY:
            raise ValueError("Cannot place an empty cell")
        if cell not in (Cell.WHITE, Cell.BLACK):
            raise ValueError("Invalid cell value")
        current_cell = self.get(position)
        if current_cell != Cell.EMPTY:
            raise ValueError("Position is already occupied")
        self.cells[position] = cell
        self.group_sizes_cache[cell] = None

    def neighbors(self, position: tuple[int, int, int],) -> tuple[tuple[int, int, int], ...]:
        return self.neighbors_map[position]

    def find_group(self, position: tuple[int, int, int]) -> list[tuple[int, int, int]]:
        if not self.contains(position):
            raise ValueError("Position is out of bounds")
        target_color = self.get(position)
        if target_color == Cell.EMPTY:
            return []
        visited = []
        to_visit = [position]
        while to_visit:
            current = to_visit.pop()
            if current not in visited:
                visited.append(current)
                for neighbor in self.neighbors(current):
                    if self.get(neighbor) == target_color and neighbor not in visited:
                        to_visit.append(neighbor)
        return visited

    def find_groups_color(self, color: Cell) -> list[list[tuple[int, int, int]]]:
        if color not in (Cell.WHITE, Cell.BLACK):
            raise ValueError("Invalid cell value")
        processed = []
        groups = []
        for position, cell in self.cells.items():
            if cell == color and position not in processed:
                group = self.find_group(position)
                groups.append(group)
                for member in group:
                    processed.append(member)
        return groups

    def group_sizes(self, color: Cell) -> list[int]:
        if self.group_sizes_cache[color] == None:
            groups = self.find_groups_color(color)
            sizes = []
            for group in groups:
                sizes.append(len(group))
            sizes.sort(reverse=True)
            self.group_sizes_cache[color] = sizes
        return self.group_sizes_cache[color].copy()

    def score(self, color: Cell) -> int:
        size = self.group_sizes(color)
        if size == []:
            return 1
        else:
            return size[0]