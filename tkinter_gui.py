from threading import Thread
import tkinter as tk
from tkinter import ttk
from typing import Optional

from game_manager import ComboResult, DoodleHistoryGame


class DoodleHistoryTkinter:
    def __init__(self, root: tk.Tk, game: DoodleHistoryGame, *, n_col: int = 2) -> None:
        self.root = root
        self.n_col = n_col

        self.game = game
        self.item1: Optional[str] = None
        self.item2: Optional[str] = None

        self._draw_gui()
        self._reset_game()

    def _draw_gui(self):
        self.root.title("Doodle History")
        self.root.geometry("600x450")

        inventory = tk.Frame(self.root)
        inventory.pack(side="left", fill="y")
        tk.Label(inventory, text="Inventory").pack()

        self.item_lists = [tk.Variable() for _ in range(self.n_col)]
        for items in self.item_lists:
            listbox = tk.Listbox(inventory, listvariable=items)
            listbox.pack(side="left", fill="y")
            listbox.bind("<<ListboxSelect>>", self._select)

        desk = tk.Frame(self.root)
        desk.pack(side="right", fill="y")
        tk.Label(desk, text="Combination History").pack()

        log = tk.Frame(desk)
        log.pack(fill="both", expand=True)

        self.log_txt = tk.Text(log, state="disabled", wrap="word")
        self.log_txt.pack(side="left", fill="y")

        self.log_txt.tag_config("null", foreground="red")
        self.log_txt.tag_config("goal", foreground="gold")

        ys = ttk.Scrollbar(log, orient="vertical", command=self.log_txt.yview)
        self.log_txt.config(yscrollcommand=ys.set)
        ys.pack(side="right", fill="y")
        
        self.mixing = tk.StringVar()
        mixing_label = tk.Label(desk, textvariable=self.mixing)
        mixing_label.pack(fill="x")

        self.combine = tk.Button(desk, text="Combine", command=self._on_click_combine, state="disabled")
        self.combine.pack()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _reset_game(self):
        self.mixing.set("Select two elements and combine them")
        for items in self.item_lists:
            items.set(list())

        self.game.reset()
        for i, elem in enumerate(sorted(self.game.obtained)):
            items = self.item_lists[i % self.n_col]
            items.set(list(items.get()) + [elem])

    def _select(self, event):
        lb: tk.Listbox = event.widget
        if not (selection := lb.curselection()):
            return
        item: str = lb.get(selection[0])
        if self.item1 is None:
            self.item1 = item
        elif self.item2 is None:
            self.item2 = item
        else:
            self.item1 = item
            self.item2 = None

        self.mixing.set(self.item1 + " + " + (self.item2 or '???'))
        self.combine.config(state="active" if self.item1 and self.item2 else "disabled")
    
    def _on_click_combine(self):
        self.log_txt.config(state="normal")
        self.log_txt.insert(tk.END ,"Thinking...\n")
        self.log_txt.config(state="disabled")

        self.root.config(cursor="watch")
        self.combine.config(state="disabled")
        t = Thread(target=self._combine, daemon=True)
        t.start()

    def _combine(self):
        if not (self.item1 and self.item2):
            raise ValueError("Both items must be selected before combining")
        result_obj = self.game.combine(self.item1, self.item2)
        self.root.after(0, lambda: self._post_combine(result_obj))
    
    def _post_combine(self, result_obj: ComboResult):
        result, desc, is_new, is_goal = result_obj
        tag = "null" if not result else ("goal" if is_goal else "")

        if self.log_txt.get("end-2c linestart", "lineend").strip() == "Thinking...\n":
            self.log_txt.delete("end-2c linestart", tk.END)

        if not (self.item1 and self.item2):
            raise ValueError("Both items must be selected before combining")
        
        self.log_txt.config(state="normal")
        self.log_txt.insert(tk.END, f"{self.item1} + {self.item2} = ")
        self.log_txt.insert(tk.END, result or "XXX", tag)
        self.log_txt.config(state="disabled")

        self.mixing.set(f"{self.item1} + {self.item2} = {result or "XXX"}")
        if is_new:
            to_update = min(self.item_lists, key=lambda var: len(tuple(var.get())))
            to_update.set(list(to_update.get()) + [result])
            if desc:
                self.log_txt.insert(tk.END, desc + "\n\n")
        
    def _on_close(self):
        self.game.close()
        self.root.destroy()


if __name__ == "__main__":
    from ai_engine import DoodleHistoryEngine

    root = tk.Tk()
    engine = DoodleHistoryEngine()
    game = DoodleHistoryGame(engine)

    DoodleHistoryTkinter(root, game)

    root.mainloop()
