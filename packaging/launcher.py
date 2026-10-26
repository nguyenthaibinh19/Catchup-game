"""Packaging entry point; game/search implementations remain unchanged."""
import multiprocessing
import os
import sys


if __name__ == '__main__':
    # Windowed executables have no terminal streams. Keep worker prints harmless.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w')
    multiprocessing.freeze_support()

    import matplotlib
    matplotlib.use('TkAgg')

    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        from frozen_smoke import run
        sys.exit(run(sys.argv[2]))

    import runpy
    runpy.run_module('main', run_name='__main__')
