import tkinter as tk

from ai_engine import DoodleHistoryEngine
from game_manager import DoodleHistoryGame
from tkinter_gui import DoodleHistoryTkinter


# Model Choices
# "gemini", "gemini-2.5-flash"
# "gemini", "gemini-3-flash-preview"
# "ollama", "deepseek-r1:8b"

root = tk.Tk()
engine = DoodleHistoryEngine("ollama", "deepseek-r1:8b")
game = DoodleHistoryGame(engine, debug=True)

DoodleHistoryTkinter(root, game)

root.mainloop()
