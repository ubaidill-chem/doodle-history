import sqlite3
from typing import NamedTuple, Optional

from google import genai
from google.genai.errors import ServerError
from pydantic import BaseModel, Field
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

client = genai.Client()

system_prompt = """System: You are an expert historian running a 20th-century logic game. The user will combine two concepts, Input A and Input B.
Available targets: ```json
{{
"Milestones": {}
"Guides": {}
"Existing Universe": {}
}}
```
Base Items: `{}`

Rules:
1. Determine if combining Input A and Input B results in a historically accurate event, concept, or invention.
2. If there is NO historical or logical connection, you must return null.
3. *Pacing*: Do not skip logical intermediate steps. Do NOT leap to highly specific events or modern inventions unless the inputs are specific enough to justify it.
4. If a valid historical result exists and it follows the pacing rule,, look at the `Milestones` list. If the result logically matches or heavily aligns with a target, you MUST output the exact name of that target.
5. If a valid historical result exists but does NOT trigger a `Milestone`, look at the `Guides` list. If it strongly aligns with an item in that list, output that exact name of that item.
6. If a valid historical result exists but does NOT match the `Guides` either, look at the `Existing Universe`. If it is a direct synonym, plural, or functionally identical concept to an item on that list, output that exact name of that item.
7. a valid historical result exists but is historically distinct from everything in the lists above, output a short, accurate 1-3 word name for the new concept.
8. If a combination feels too generic or repetitive, try to find a more specific, technical, or localized historical term.

If a valid historical result exists, also return 
- `desc`: A brief, punchy historical connection (maximum 15 words).
- `meta`: Your meta thought process considering the greater scheme of the game such as how your choosen result will interact with the `Existing Universe` or help the player reach the `Milestones`.
Output format: JSON only. `{{"result": "Output Name", "desc": "Description", "meta": "Thought"}}` or `{{"result": null, "desc": null, "meta": null}}`"""


class ComboResult(BaseModel):
    result: Optional[str] = None
    desc: Optional[str] = Field(default=None, description="A brief, punchy historical connection (maximum 15 words).")
    meta: Optional[str] = Field(default=None, description="Meta thought process on how this result would work with other items or the goals of the game.")


class DBResult(NamedTuple):
    is_cached: bool
    result_obj: ComboResult


class DoodleHistoryEngine:
    def __init__(self) -> None:
        with sqlite3.connect("combinations.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, is_base, is_guide, is_goal FROM items")
            rows = cursor.fetchall()

            self.base_elems = [x[0] for x in rows if x[1]]
            self.guide_elems = [x[0] for x in rows if x[2]]
            self.goal_elems = [x[0] for x in rows if x[3]]
            self.other_elems = [x[0] for x in rows if not any(x[1:])]

    def _try_combine(self, cursor: sqlite3.Cursor, item1_id: int, item2_id: int) -> DBResult:
        cursor.execute("""
            SELECT items.name, recipe.desc, recipe.meta
            FROM recipe
            LEFT JOIN items ON recipe.result_id = items.id
            WHERE recipe.item1_id = ? AND recipe.item2_id = ?
        """, (item1_id, item2_id))
        
        if row := cursor.fetchone():
            return DBResult(True, ComboResult(result=row[0], desc=row[1], meta=row[2]))
        return DBResult(False, ComboResult())

    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(4), retry=retry_if_exception_type(ServerError))
    def _prompt_genai(self, item1: str, item2: str) -> ComboResult:
        user_prompt = f"Combine {item1} and {item2}"
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=user_prompt,
            config={
                "system_instruction": system_prompt.format(self.goal_elems, self.guide_elems, self.other_elems, self.base_elems),
                "response_mime_type": "application/json",
                "response_schema": ComboResult
            }
        )
        result: ComboResult = response.parsed # type: ignore
        return result

    def combine(self, item1: str, item2: str) -> ComboResult:
        with sqlite3.connect("combinations.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM items WHERE name = ?", (item1,))
            item1_id = cursor.fetchone()[0]

            cursor.execute("SELECT id FROM items WHERE name = ?", (item2,))
            item2_id = cursor.fetchone()[0]

            item1_id, item2_id = sorted((item1_id, item2_id))
            is_cached, result = self._try_combine(cursor, item1_id, item2_id)
            if is_cached:
                return result
            
            result_obj = self._prompt_genai(item1, item2)

            result = result_obj.result
            result_id = None
            if result:
                if result not in self.other_elems:
                    self.other_elems.append(result)
                cursor.execute("INSERT OR IGNORE INTO items (name) VALUES (?)", (result,))
                cursor.execute("SELECT id FROM items WHERE name = ?", (result,))
                result_id = cursor.fetchone()[0]

            cursor.execute(
                "INSERT OR IGNORE INTO recipe (item1_id, item2_id, result_id, desc, meta) VALUES (?, ?, ?, ?, ?)", 
                (item1_id, item2_id, result_id, result_obj.desc, result_obj.meta)
            )

        return result_obj
