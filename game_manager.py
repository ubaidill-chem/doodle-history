from typing import NamedTuple, Optional

from ai_engine import DoodleHistoryEngine


class ComboResult(NamedTuple):
    result: Optional[str]
    desc: Optional[str]
    new_elem: bool
    did_obtain_goal: bool

class DoodleHistoryGame:
    def __init__(self, engine: DoodleHistoryEngine):
        self.engine = engine
        self.base: set[str] = set(engine.base_elems)
        self.goal: set[str] = set(engine.goal_elems)
        self.guide: set[str] = set(engine.guide_elems)

        self.is_obtained: dict[str, bool] = {x: False for x in self.base | self.goal | self.guide}
        self.reset()
        
    @property
    def obtained(self) -> set[str]:
        obtained = {elem for elem, is_obtained in self.is_obtained.items() if is_obtained}
        return obtained
    
    @property
    def progress(self):
        prog = len(self.goal & self.obtained) / len(self.goal)
        return prog
    
    def reset(self):
        for base in self.base:
            self.is_obtained[base] = True

    def combine(self, item1: str, item2: str) -> ComboResult:
        result_obj = self.engine.combine(item1, item2)
        result = result_obj.result
        desc = result_obj.desc

        new_elem = False
        did_obtain_goal = False
        if result and result not in self.obtained:
            self.is_obtained[result] = True
            new_elem = True
            did_obtain_goal = (result in self.goal)
        
        return ComboResult(result, desc, new_elem, did_obtain_goal)
