import sqlite3
from typing import NamedTuple, Optional

from google import genai
from pydantic import BaseModel, Field

client = genai.Client()

system_prompt = """System: You are an expert historian running a 20th-century logic game. The user will combine two concepts, Input A and Input B.
Available Targets: ```json
{
"Milestones": {target_elems}
"Guides": {guide_elems}
}
```

Rules:
1. Determine if combining Input A and Input B results in a historically accurate event, concept, or invention.
2. If there is NO historical or logical connection, you must return null.
3. If there is a connection, look at the `Milestones` list. If the result logically matches or heavily aligns with a target, you MUST output the exact name of that target.
4. If a valid historical result exists but does NOT trigger a `Milestone`, look at the `Guides` list. If it strongly aligns with an item in that list, output that exact name of that item.
5. If a valid historical result exists but does NOT match any available items, output a short, accurate 1-3 word name for the new concept.
6. If a valid historical result exists, also return a one sentence description or justification of why that result was choosen.

Output format: JSON only. `{"result": "Output Name", "desc": "Description"}` or `{"result": null, "desc": null}`"""


class ComboResult(BaseModel):
    result: Optional[str] = None
    desc: Optional[str] = Field(default=None, description="One sentence of description or justification of the combination result")


class DBResult(NamedTuple):
    is_cached: bool
    result_obj: ComboResult


class DoodleHistoryEngine:
    def __init__(self) -> None:
        self.conn = sqlite3.connect("combinations.db")
        self.cursor = self.conn.cursor()

        self.cursor.execute("SELECT name FROM items WHERE is_goal = TRUE")
        self.target_elems = [x[0] for x in self.cursor.fetchall()]

        self.cursor.execute("SELECT name FROM items WHERE is_guide = TRUE")
        self.guide_elems = [x[0] for x in self.cursor.fetchall()]

    def close(self):
        self.conn.close()

    def _try_combine(self, item1_id: int, item2_id: int) -> DBResult:
        self.cursor.execute("""
            SELECT items.name recipe.desc
            FROM recipe
            LEFT JOIN items ON recipe.result_id = items.id
            WHERE recipe.item1_id = ? AND recipe.item2_id = ?
        """, (item1_id, item2_id))
        
        if row := self.cursor.fetchone():
            return DBResult(True, ComboResult(result=row[0], desc=row[1]))
        return DBResult(False, ComboResult())

    def _prompt_genai(self, item1: str, item2: str) -> ComboResult:
        user_prompt = f"Combine {item1} and {item2}"
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=user_prompt,
            config={
                "system_instruction": system_prompt.format(self.target_elems, self.guide_elems),
                "response_mime_type": "application/json",
                "response_schema": ComboResult
            }
        )
        return response.parsed # type: ignore

    def combine(self, item1: str, item2: str) -> ComboResult:
        self.cursor.execute("SELECT id FROM items WHERE name = ?", (item1,))
        item1_id = self.cursor.fetchone()[0]

        self.cursor.execute("SELECT id FROM items WHERE name = ?", (item2,))
        item2_id = self.cursor.fetchone()[0]

        item1_id, item2_id = sorted((item1_id, item2_id))
        is_cached, result = self._try_combine(item1_id, item2_id)
        if is_cached:
            return result
        
        result_obj = self._prompt_genai(item1, item2)

        result = result_obj.result
        result_id = None
        if result:
            self.cursor.execute("INSERT OR IGNORE INTO items (name) VALUES (?)", (result,))
            self.cursor.execute("SELECT id FROM items WHERE name = ?", (result,))
            result_id = self.cursor.fetchone()[0]

        self.cursor.execute(
            "INSERT OR IGNORE INTO recipe (item1_id, item2_id, result_id, desc) VALUES (?, ?, ?, ?)", 
            (item1_id, item2_id, result_id, result_obj.desc)
        )

        self.conn.commit()
        return result_obj
