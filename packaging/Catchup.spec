# Build from the project root:
#   python -B -m PyInstaller --noconfirm --clean --distpath dist --workpath build/catchup_release packaging/Catchup.spec
from pathlib import Path

support = Path(SPECPATH)
project = support.parent
a = Analysis(
    [str(support / 'launcher.py')],
    pathex=[str(project), str(support)],
    binaries=[],
    datas=[],
    hiddenimports=[
        'main',
        'src.game',
        'src.board',
        'src.display',
        'bot.strong_bot',
        'bot.core',
        'bot.movegen',
        'bot.strong_eval',
        'bot.minimax_bot',
        'bot.random_bot',
        'bot.evaluation',
    ],
    hookspath=[],
    runtime_hooks=[],
    hooksconfig={'matplotlib': {'backends': ['TkAgg']}},
    excludes=[
        'IPython', 'ipykernel', 'jupyter', 'notebook', 'torch',
        'tensorflow', 'scipy', 'pandas', 'sympy', 'pytest',
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='Catchup',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
