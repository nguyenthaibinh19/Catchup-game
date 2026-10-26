from src.game import Game
from src.display import choose_color, plot
from bot.strong_bot import iterative_move

if __name__ == "__main__":
    human_color = choose_color()
    if human_color != None:
        game = Game(radius=4)
        plot(game,human_color)

