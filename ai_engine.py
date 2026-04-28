import sqlite3
from typing import NamedTuple, Optional

from google import genai
from google.genai.errors import ServerError
from pydantic import BaseModel, Field
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

client = genai.Client()

system_prompt = """You are an expert historian. You analyze history through the interaction of material conditions, economics, and power structures.

## Game context
Milestones (primary goals): {milestones}
Guides (intermediate stepping stones): {guides}
Base items (always available): {base}

## Combination logic
Given two input items, determine the single most historically coherent result.

Priority order:
1. If the result is an exact or near-exact match to a Milestone, return the Milestone name verbatim.
2. Else if the result maps to a Guide, return the Guide name verbatim.
3. Else if a strong causal or thematic link exists, generate a 1–3 word historical concept. The link must be direct — no chronological leaps. Intermediate concepts must be discoverable before their dependents.
4. Else return null.

Analytical lens: Favor results that reveal how material conditions (land, labor, resources), capital formation, and social structures interact to produce historical outcomes.

## Output format
JSON only. No explanation outside the JSON object.
{"result": string|null, "desc": string|null, "meta": string|null}

- `result`: The output item name, or null.
- `desc`: Max 15 words. A punchy causal connection. Null if result is null.  
- `meta`: One sentence. How this item connects to other discoverable items or game goals. Null if result is null."""


class ComboResult(BaseModel):
    result: Optional[str] = None
    desc: Optional[str] = Field(default=None, description="A brief, punchy causal connection (maximum 15 words).")
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
                "system_instruction": system_prompt.format(self.goal_elems, self.guide_elems, self.base_elems),
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
                cursor.execute("INSERT OR IGNORE INTO items (name) VALUES (?)", (result,))
                cursor.execute("SELECT id FROM items WHERE name = ?", (result,))
                result_id = cursor.fetchone()[0]

            cursor.execute(
                "INSERT OR IGNORE INTO recipe (item1_id, item2_id, result_id, desc, meta) VALUES (?, ?, ?, ?, ?)", 
                (item1_id, item2_id, result_id, result_obj.desc, result_obj.meta)
            )

        return result_obj
