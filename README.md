# Catchup

Hex placement game for two players (you vs the AI). White moves first. The winner is the player with the lexicographically largest group-size vector — in practice, the largest connected group of stones.

**Windows 64-bit:** download `Catchup.exe` from [Releases](https://github.com/nguyenthaibinh19/Catchup-game/releases). No Python install is required.

## How to play

1. Choose **Play WHITE** or **Play BLACK**. The AI takes the other color.
2. Click empty hexes to place stones.
3. When you select the maximum number of stones allowed, the move is submitted automatically. Press **Enter** to submit fewer stones.
4. **Undo** clears the current selection, or restores your previous turn if nothing is selected.
5. The AI thinks for about **15 seconds** per move. Keep the window open while it is thinking.

The number of stones you may place:

- First move of the game: 1
- Normally: up to 2
- Catch-up: 3, when the opponent just grew their largest group and you are not ahead

## Run from source

Python 3.10+ on Windows:

```text
pip install -r requirements.txt
python main.py
```

## Build the Windows exe

From the project root, with matplotlib and PyInstaller installed:

```text
python -B -m PyInstaller --noconfirm --clean --distpath dist --workpath build/catchup_release packaging/Catchup.spec
```

The output is `dist/Catchup.exe`.
