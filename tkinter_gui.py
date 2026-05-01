from threading import Thread
import tkinter as tk
from tkinter import ttk
from typing import Optional

from tenacity import RetryError

from game_manager import ComboResult, DoodleHistoryGame


class DoodleHistoryTkinter:
    def __init__(self, root: tk.Tk, game: DoodleHistoryGame, *, n_col: int = 2) -> None:
        self.root = root
        self.n_col = n_col
        self.game = game
        
        self.item1: Optional[str] = None
        self.item2: Optional[str] = None
        self.thinking = False

        self._draw_gui()
        self._reset_game()

    def toggle_thinking(self):
        self.thinking = not self.thinking
        self.log_txt.config(state="normal")

        if self.thinking:
            self.log_txt.insert(tk.END, "Thinking...")
            self.log_txt.see(tk.END)
            self.root.config(cursor="watch")
            self.combine.config(state="disabled")
        else:
            if self.log_txt.get("1.0", tk.END).endswith("Thinking...\n"):
                self.log_txt.delete("end-12c", "end-1c")
            self.root.config(cursor="")
            self.combine.config(state="active")
        
        self.log_txt.config(state="disabled")

    def _draw_gui(self):
        self.root.title("Doodle History")
        self.root.geometry("700x450")

        inventory = tk.Frame(self.root)
        inventory.pack(side="left", fill="y")
        tk.Label(inventory, text="Inventory").pack()

        self.item_lists = [tk.Variable() for _ in range(self.n_col)]
        for items in self.item_lists:
            listbox = tk.Listbox(inventory, listvariable=items)
            listbox.pack(side="left", fill="y")
            listbox.bind("<<ListboxSelect>>", self._select)

        desk = tk.Frame(self.root)
        desk.pack(side="right", fill="both", expand=True)
        tk.Label(desk, text="Combination History").pack()

        log = tk.Frame(desk)
        log.pack(fill="both", expand=True)

        self.log_txt = tk.Text(log, state="disabled", wrap="word")
        self.log_txt.pack(side="left", fill="both", expand=True)

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

    def _reset_game(self):
        self.mixing.set("Select two elements and combine them")
        for items in self.item_lists:
            items.set(list())

        self.game.reset()
        for i, elem in enumerate(self.game.obtained):
            items = self.item_lists[i % self.n_col]
            items.set(list(items.get()) + [elem])

    def _select(self, event):
        if self.thinking:
            return
        
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
        self.toggle_thinking()
        t = Thread(target=self._combine, daemon=True)
        t.start()

    def _combine(self):
        if not (self.item1 and self.item2):
            raise ValueError("Both items must be selected before combining")
        
        try:
            result_obj = self.game.combine(self.item1, self.item2)
            self.root.after(0, lambda: self._post_combine(result_obj))
        except Exception as e:
            self.root.after(0, lambda err=e: self._handle_error(err))
    
    def _post_combine(self, result_obj: ComboResult):
        item1, item2, result, desc, is_new, is_goal = result_obj
        tag = "goal" if is_goal else ("null" if not result else "")
        self.toggle_thinking()

        self.log_txt.config(state="normal")

        self.log_txt.insert(tk.END, f"{item1} + {item2} = ")
        self.log_txt.insert(tk.END, (result or "XXX") + "\n", tag)
        if is_new and desc:
            self.log_txt.insert(tk.END, desc + "\n\n")

        self.log_txt.config(state="disabled")
        self.log_txt.see(tk.END)

        self.mixing.set(f"{item1} + {item2} = {result or "XXX"}")
        if is_new and result:
            items = self.item_lists[(len(self.game.obtained) - 1) % self.n_col]
            items.set(list(items.get()) + [result])

    def _handle_error(self, error):
        if isinstance(error, RetryError):
            error = error.last_attempt.exception()
            
        self.toggle_thinking()
        print(error)

        self.log_txt.config(state="normal")
        self.log_txt.insert(tk.END, f"API Error: {str(error)[:50]}\n", "null")
        self.log_txt.config(state="disabled")
        self.log_txt.see(tk.END)

        self.combine.config(state="active")
