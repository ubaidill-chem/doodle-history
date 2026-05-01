import argparse
import tkinter as tk

from ai_engine import DoodleHistoryEngine
from game_manager import DoodleHistoryGame
from tkinter_gui import DoodleHistoryTkinter


# Model Choices
# "gemini", "gemini-2.5-flash"
# "gemini", "gemini-3-flash-preview"
# "ollama", "deepseek-r1:8b"

parser = argparse.ArgumentParser(description="Doodle History - An AI-powered history game")
parser.add_argument(
    "--provider",
    type=str,
    default="gemini",
    help="AI provider (e.g., 'gemini', 'ollama'). Default: gemini"
)
parser.add_argument(
    "--model",
    type=str,
    default="gemini-3-flash-preview",
    help="AI model to use. Default: gemini-3-flash-preview"
)
parser.add_argument(
    "--debug",
    action="store_true",
    help="Enable debug mode (unlocks all combinations)"
)
args = parser.parse_args()

root = tk.Tk()
engine = DoodleHistoryEngine(provider=args.provider, model=args.model)
game = DoodleHistoryGame(engine, debug=args.debug)

DoodleHistoryTkinter(root, game)

root.mainloop()
