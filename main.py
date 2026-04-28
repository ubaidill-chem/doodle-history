import tkinter as tk

from ai_engine import DoodleHistoryEngine
from game_manager import DoodleHistoryGame
from tkinter_gui import DoodleHistoryTkinter


root = tk.Tk()
engine = DoodleHistoryEngine()
game = DoodleHistoryGame(engine)

DoodleHistoryTkinter(root, game)

root.mainloop()
