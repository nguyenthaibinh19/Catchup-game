import math

import matplotlib.pyplot as plt
from matplotlib.patches import RegularPolygon
from matplotlib.widgets import Button
from src.game import Game
from src.board import Board, Cell
from bot.minimax_bot import minimax_move
from bot.random_bot import move_random
from bot.strong_bot import iterative_move
from time import perf_counter
from concurrent.futures import ProcessPoolExecutor
from time import perf_counter
hexsize = 1.0

def cube(x: int, y: int, z: int, hexsize: float) -> tuple[float, float]:
    pixel_x = hexsize * math.sqrt(3) * (x + y / 2)
    pixel_y = hexsize * 1.5 * y
    return pixel_x, pixel_y
def choose_color()-> Cell | None:
    select_color = {"color": None}
    figure, axe = plt.subplots(figsize=(5, 3))
    axe.axis("off")
    figure.suptitle("Choose your color", fontsize=16)
    white_color = figure.add_axes([0.15, 0.3, 0.3, 0.2])
    black_color = figure.add_axes([0.55, 0.3, 0.3, 0.2])
    white_button = Button(white_color, "Play WHITE", color="white", hovercolor="lightgray")
    black_button = Button(black_color, "Play BLACK", color="black", hovercolor="lightgray")
    black_button.label.set_color("white")
    def choose_white(event):
        select_color["color"] = Cell.WHITE
        plt.close(figure)
    def choose_black(event):
        select_color["color"] = Cell.BLACK
        plt.close(figure)
    white_button.on_clicked(choose_white)
    black_button.on_clicked(choose_black)
    plt.show()
    return select_color["color"]
def plot (game:Game, human_color:Cell) ->None:
    if human_color == Cell.WHITE:
        bot_color = Cell.BLACK
    else:
        bot_color = Cell.WHITE
    history = []
    board = game.board
    selected_positions = []
    figure, axe = plt.subplots(figsize=(9, 9))
    figure.subplots_adjust(bottom=0.24)
    executor = ProcessPoolExecutor(max_workers=1)
    bot_future = None
    bot_started = 0
    closed = False
    timer = figure.canvas.new_timer(interval=100)
    scoreboard = figure.text(
        0.5,
        0.12,
        "",
        horizontalalignment="center",
        verticalalignment="bottom",
        fontsize=11,
    )
    undo_axe = figure.add_axes([0.40, 0.02, 0.20, 0.05])
    undo_button = Button(undo_axe, "Undo", color="lightgray", hovercolor="gray")
    hexagons = {}

    for position, cell in board.cells.items():
        x, y, z = position

        pixel_x, pixel_y = cube(x, y, z, hexsize)
        if cell == Cell.EMPTY:
            cell_color = 'lightgray'
        elif cell == Cell.WHITE:
            cell_color = 'white'
        else:
            cell_color = 'black'

        hexagon = RegularPolygon((pixel_x, pixel_y), numVertices=6, radius=hexsize, orientation=0, facecolor=cell_color, edgecolor='gray',linewidth=0.8)
        axe.add_patch(hexagon)
        hexagons[position] = hexagon

        if cell is Cell.BLACK:
            text_color = "white"
        else:
            text_color = "black"

        axe.text(
            pixel_x,
            pixel_y,
            f"{x},{y},{z}",
            horizontalalignment="center",
            verticalalignment="center",
            fontsize=7,
            color=text_color,
        )
    def refresh_display():
        for position, hexagon in hexagons.items():
            cell = board.get(position)
            if position in selected_positions:
                cell = game.current_player
                hexagon.set_edgecolor("red")
            else:
                hexagon.set_edgecolor("gray")
            if cell == Cell.EMPTY:
                cell_color = 'lightgray'
            elif cell == Cell.WHITE:
                cell_color = 'white'
            else:
                cell_color = 'black'
            hexagon.set_facecolor(cell_color)
        white_score = board.score(Cell.WHITE)
        black_score = board.score(Cell.BLACK)

        white_groups = board.group_sizes(Cell.WHITE)
        black_groups = board.group_sizes(Cell.BLACK)

        scoreboard.set_text(
            f"WHITE — Score: {white_score}\n"
            f"Groups: {white_groups}\n"
            f"BLACK — Score: {black_score}\n"
            f"Groups: {black_groups}"
        )

        if game.game_over():
            winner = game.winner()

            if winner == Cell.WHITE:
                axe.set_title("GAME OVER — WHITE WINS!", fontsize=15)
            elif winner == Cell.BLACK:
                axe.set_title("GAME OVER — BLACK WINS!", fontsize=15)
            else:
                axe.set_title("GAME OVER — DRAW!", fontsize=15)
        else:
            if game.current_player == human_color:
                player_text = "YOUR TURN"
            else:
                player_text = "BOT TURN"
            axe.set_title(
                f"{player_text} — {game.current_player.name}\n"
                f"Selected: {len(selected_positions)}/{game.max_move()} | "
                f"You: {human_color.name} | Bot: {bot_color.name}\n"
                "Press Enter to finish your turn",
                fontsize=12,
            )
        figure.canvas.draw_idle()
    def start_bot():
        nonlocal bot_future,bot_started
        if closed or game.game_over():
            return
        if game.current_player != bot_color:
            return
        if bot_future != None:
            return
        bot_started = perf_counter()

        bot_future = executor.submit(iterative_move,game.copy(),time_limit=15)
        axe.set_title ("thinking")
        figure.canvas.draw_idle()
        timer.start()
    def check_bot():
        nonlocal bot_future

        if closed or bot_future is None:
            return

        if not bot_future.done():
            return

        timer.stop()
        finished = bot_future
        bot_future = None

        try:
            move = finished.result()
        except Exception as error:
            print(f"Bot error: {error}")
            axe.set_title("Bot gặp lỗi — xem terminal")
            figure.canvas.draw_idle()
            return

        elapsed = perf_counter() - bot_started
        print("Bot selected:", move)
        print(f"Waiting time: {elapsed:.3f} seconds")

        game.play(move)
        refresh_display()


    def handle_close(event):
        nonlocal closed

        closed = True
        timer.stop()
        executor.shutdown(wait=False, cancel_futures=True)
    def finish_turn():
        if game.game_over():
            return
        if bot_future !=None:
            return
        if game.current_player != human_color:
            return
        if not selected_positions:
            return
        history.append(game.copy())
        game.play(selected_positions)
        selected_positions.clear()
        refresh_display()
        #if game.game_over():
            #winner = game.winner()
            #if winner is None:
                #print("Game over! It's a tie.")
            #elif winner == Cell.WHITE:
                #print("Game over! White wins.")
            #else:
                #print("Game over! Black wins.")
        start_bot()

    def handle_click(event):
        if bot_future != None:
            return
        if event.button != 1:
            return
        if event.inaxes != axe:
            return
        if game.game_over():
            return
        if game.current_player != human_color:
            return
        for position, hexagon in hexagons.items():
            clicked_inside, details = hexagon.contains(event)

            if clicked_inside:
                if board.get(position) != Cell.EMPTY:
                    return

                if position in selected_positions:
                    return

                selected_positions.append(position)

                if len(selected_positions) == game.max_move():
                    finish_turn()
                else:
                    refresh_display()

                return
    def undo_move(event= None):
        nonlocal game,board
        if bot_future != None:
            return
        if selected_positions:
            selected_positions.clear()
            refresh_display()
            return
        if not history:
            return
        game = history.pop()
        board = game.board
        selected_positions.clear()
        refresh_display()
    def handle_key(event):
        if event.key == "enter":
            finish_turn()
    undo_button.on_clicked(undo_move)
    figure.canvas.mpl_connect(
        "button_press_event", handle_click
    )
    figure.canvas.mpl_connect(
        "key_press_event", handle_key
    )

    axe.set_aspect("equal")
    axe.autoscale_view()
    axe.axis("off")

    refresh_display()
    timer.add_callback(check_bot)
    figure.canvas.mpl_connect("close_event", handle_close)

    refresh_display()
    start_bot()
    plt.show()


