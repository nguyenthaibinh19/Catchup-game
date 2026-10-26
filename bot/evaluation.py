from src.board import Cell
from src.game import Game

def group_expansion(game:Game, group:list[tuple[int,int,int]]):
    empty_neighbors = set()
    for position in group:
        for i in game.board.neighbors(position):
            if game.board.get(i) == Cell.EMPTY:
                empty_neighbors.add(i)
    return empty_neighbors

def largest_expansion (game:Game, color:Cell) -> int:
    groups = game.board.find_groups_color(color)
    if not groups:
        return 0
    largest_size = max(len(i) for i in groups)
    largest_groups = []
    for i in groups:
        if len(i) == largest_size:
            largest_groups.append(i)
    expansion = []
    for i in largest_groups:
        expansion.append(len(group_expansion(game,i)))
    return max(expansion)

def group_size (game:Game, color:Cell) ->list[int]:
    group = game.board.find_groups_color(color)
    size = []
    for i in group:
        size.append(len(i))
    size.sort(reverse=True)
    return size

def structure_value (game:Game,color:Cell) -> float:
    size = group_size(game,color)
    if len(size) <=1:
        return 0.0
    value = 0.0
    for i in range(1, len(size)):
        k = size[i]
        value += k / (2** i)
    return value

def evaluation_features(game:Game, bot_color:Cell):
    if bot_color == Cell.WHITE:
        opponent= Cell.BLACK
    else:
        opponent= Cell.WHITE
    bot_score = game.board.score(bot_color)
    opponent_score = game.board.score(opponent)
    bot_expansion = largest_expansion(game,bot_color)
    opponent_expansion = largest_expansion(game,opponent)
    return{
        "bot_score":bot_score,
        "opponent_score": opponent_score,
        "score_diff": bot_score - opponent_score,
        "bot_expansion": bot_expansion,
        "opponent_expansion": opponent_expansion,
        "expansion_diff": bot_expansion - opponent_expansion,
    }





############################################################################ EVALUATION PART #####################################################################





def evaluate(game:Game, bot_color:Cell) -> float:
    if game.game_over ():
        winner = game.winner()
        if winner is None:
            return 0
        if winner == bot_color:
            return float ("inf")
        else:
            return float("-inf")
    # 3. Xác định màu đối thủ.
    if bot_color == Cell.WHITE:
        opponent = Cell.BLACK
    else:
        opponent = Cell.WHITE
    bot_score = game.board.score(bot_color)
    opponent_score = game.board.score(opponent)
    return float (bot_score - opponent_score)

def evaluate_v2(game:Game, bot_color:Cell, expansion_weight:float = 0.25) -> float:
    if game.game_over():
        winner = game.winner()
        if winner == None:
            return 0.0
        if winner == bot_color:
            return float("inf")
        return float("-inf")
    if bot_color ==  Cell.WHITE:
        opponent = Cell.BLACK
    else:
        opponent = Cell.WHITE
    bot_score = game.board.score(bot_color)
    opponent_score = game.board.score(opponent)
    bot_expansion = largest_expansion(game,bot_color)
    opponent_expansion = largest_expansion(game,opponent)
    score_diff = bot_score - opponent_score
    expansion_diff = bot_expansion - opponent_expansion
    return float(score_diff +expansion_weight * expansion_diff)

def evaluate_v3(game:Game, bot_color:Cell,expansion_weight:float = 0.25,structure_weight:float = 0.25) ->float:
    if game.game_over():
        winner = game.winner()
        if winner == None:
            return 0.0
        if winner == bot_color:
            return float("inf")
        return float("-inf")
    if bot_color == Cell.WHITE:
        opponent = Cell.BLACK
    else:
        opponent = Cell.WHITE
    bot_score = game.board.score(bot_color)
    opponent_score = game.board.score(opponent)
    bot_expansion = largest_expansion(game, bot_color)
    opponent_expansion = largest_expansion(game, opponent)
    bot_structure = structure_value(game, bot_color)
    opponent_structure = structure_value(game, opponent)
    score_diff = bot_score - opponent_score
    expansion_diff = bot_expansion - opponent_expansion
    structure_diff = bot_structure - opponent_structure
    return float(score_diff+ expansion_weight * expansion_diff+ structure_weight * structure_diff)
        




