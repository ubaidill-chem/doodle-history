from typing import NamedTuple, Optional

from ai_engine import DoodleHistoryEngine


class ComboResult(NamedTuple):
    item1: str
    itee2: str
    result: Optional[str]
    desc: Optional[str]
    new_elem: bool
    did_obtain_goal: bool

class DoodleHistoryGame:
    def __init__(self, engine: DoodleHistoryEngine, *, debug=False):
        self.engine = engine
        self.debug = debug

        self.base: list[str] = engine.base_elems
        self.goal: list[str] = engine.goal_elems
        self.guide: list[str] = engine.guide_elems

        self.is_obtained: dict[str, bool] = {x: False for x in self.base + self.goal + self.guide}
        self.reset()
        
    @property
    def obtained(self) -> list[str]:
        obtained = [elem for elem, is_obtained in self.is_obtained.items() if is_obtained]
        return obtained
    
    @property
    def progress(self):
        prog = len(set(self.goal) & set(self.obtained)) / len(self.goal)
        return prog
    
    def reset(self):
        for base in self.base:
            self.is_obtained[base] = True
        if self.debug:
            for res in self.engine._get_recipe_results():
                self.is_obtained[res[0]] = True

    def combine(self, item1: str, item2: str) -> ComboResult:
        result_dict = self.engine.combine(list(self.obtained), item1, item2)
        result = result_dict["result"]
        desc = result_dict["desc"]

        new_elem = False
        did_obtain_goal = False
        if result and result not in self.obtained:
            self.is_obtained[result] = True
            new_elem = True
            did_obtain_goal = (result in self.goal)
        
        return ComboResult(item1, item2, result, desc, new_elem, did_obtain_goal)
