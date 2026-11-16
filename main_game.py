"""
Shortcut: open the combined launcher directly in Single Player mode.

Run game.py instead if you want the mode menu (Single Player / Online).
"""

from game import CarGame

if __name__ == "__main__":
    CarGame(start_mode="single").run()
