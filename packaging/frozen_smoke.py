"""Opt-in packaged-app integration check, never used during normal play."""
import json
from pathlib import Path
from time import perf_counter, sleep
import traceback


def run(output_path):
    report = {'status': 'RUNNING', 'checks': []}
    output = Path(output_path)
    original_show = None
    try:
        import sys
        import matplotlib
        import matplotlib.pyplot as plt
        from matplotlib.backend_bases import MouseEvent
        from src.board import Cell
        from src.game import Game
        from src import display

        report.update(frozen=bool(getattr(sys, 'frozen', False)),
                      backend=matplotlib.get_backend(), executable=sys.executable)
        assert report['frozen']
        assert report['backend'].lower() == 'tkagg'
        original_show = plt.show

        def click_axis(fig, ax):
            fig.canvas.draw()
            x, y = ax.transAxes.transform((0.5, 0.5))
            for name in ('button_press_event', 'button_release_event'):
                event = MouseEvent(name, fig.canvas, x, y, button=1)
                fig.canvas.callbacks.process(name, event)

        for color, axis_index in ((Cell.WHITE, 1), (Cell.BLACK, 2)):
            def choose_show(*args, **kwargs):
                fig = plt.gcf()
                fig.canvas.manager.window.withdraw()
                click_axis(fig, fig.axes[axis_index])
            plt.show = choose_show
            assert display.choose_color() == color
            report['checks'].append('choose_' + color.name)

        for human_color in (Cell.BLACK, Cell.WHITE):
            game = Game(radius=4)
            minimum_stones = 1 if human_color == Cell.BLACK else 2
            maximum_stones = 1 if human_color == Cell.BLACK else 4
            def game_show(*args, **kwargs):
                fig = plt.gcf()
                window = fig.canvas.manager.window
                window.withdraw()
                fig.canvas.draw()
                assert len(fig.axes[0].patches) == 61
                if human_color == Cell.WHITE:
                    patch = fig.axes[0].patches[0]
                    x, y = fig.axes[0].transData.transform(patch.xy)
                    fig.canvas.callbacks.process('button_press_event',
                        MouseEvent('button_press_event', fig.canvas, x, y, button=1))
                started = perf_counter()
                while perf_counter() - started < 45:
                    window.update()
                    occupied = sum(c != Cell.EMPTY for c in game.board.cells.values())
                    if occupied >= minimum_stones and game.current_player == human_color:
                        break
                    if 'Bot gặp lỗi' in fig.axes[0].get_title():
                        raise AssertionError('GUI reported a worker error')
                    sleep(0.02)
                else:
                    raise AssertionError('GUI bot turn did not complete within 45 seconds')
                assert minimum_stones <= occupied <= maximum_stones, occupied
                assert 'YOUR TURN' in fig.axes[0].get_title()
                report['checks'].append({'human': human_color.name,
                    'occupied': occupied, 'bot_turn_seconds': perf_counter() - started,
                    'title': fig.axes[0].get_title()})
                fig.savefig(output.with_name('frozen_' + human_color.name.lower() + '.png'))
                plt.close(fig)
            plt.show = game_show
            display.plot(game, human_color)
        report['status'] = 'PASS'
        return_code = 0
    except BaseException:
        report['status'] = 'FAIL'
        report['traceback'] = traceback.format_exc()
        return_code = 1
    finally:
        if original_show is not None:
            plt.show = original_show
            plt.close('all')
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    return return_code
