import re
import sqlite3
from typing import Optional

from google import genai
from google.genai.errors import ServerError
import ollama
from pydantic import BaseModel, Field
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from db_setup import embed_and_store, get_embed_blob, load_sqlite_vec


MIN_DIST = 0.15
client = genai.Client()

class ComboResult(BaseModel):
    result: Optional[str] = None
    desc: Optional[str] = Field(
        default=None, description="A brief, punchy causal connection (maximum 15 words)."
    )
    meta: Optional[str] = Field(
        default=None, 
        description="Meta thought process on how this result would work with other items or the goals of the game."
    )
    tier: Optional[int] = Field(
        default=None,
        description="Precedence tier used: 1=Milestone, 2=Guide, 3=Novel concept, null if no valid result."
    )


class DoodleHistoryEngine:
    def __init__(self, provider: str = "gemini", model: str = "gemini-3-flash-preview") -> None:
        self.provider = provider
        self.model = model

        with sqlite3.connect("combinations.db") as conn:
            load_sqlite_vec(conn)
            cursor = conn.cursor()
            cursor.execute("SELECT name, is_base, is_guide, is_goal FROM items")
            rows = cursor.fetchall()

            self.base_elems = [x[0] for x in rows if x[1]]
            self.guide_elems = [x[0] for x in rows if x[2]]
            self.goal_elems = [x[0] for x in rows if x[3]]
        
        self.system_prompt = f"""You are an expert historian. You analyze history through the interaction of material conditions, economics, and power structures.

## Game context
Milestones (primary goals): 
{', '.join(self.goal_elems)}
Guides (intermediate stepping stones): 
{', '.join(self.guide_elems)}
Base items (always available): 
{', '.join(self.base_elems)}

## Combination logic
Given two input items, determine the single most historically coherent result.

Priority order:
1. If the result is an exact or near-exact match to a Milestone, return the Milestone name verbatim.
2. Else if the result maps to a Guide, return the Guide name verbatim.
3. Else if a strong causal or thematic link exists, generate a 1–3 word historical concept. The link must be direct, no chronological leaps. Intermediate concepts must be discoverable before their dependents.
4. Else return null.

Analytical lens: Favor results that reveal how material conditions (land, labor, resources), capital formation, and social structures interact to produce historical outcomes.

## Output format
Respond strictly in valid JSON format matching the provided schema. Do not include any conversational filler
{{"result": string|null, "desc": string|null, "meta": string|null}}

- `result`: The output item name, or null.
- `desc`: Max 15 words. A punchy causal connection. Null if result is null.  
- `meta`: One sentence. How this item connects to other discoverable items or game goals. Null if result is null.
- `tier`: 1 if result is a Milestone, 2 if a Guide, 3 if a novel concept, null if result is null.
"""

    def _try_combine(self, cursor: sqlite3.Cursor, item1_id: int, item2_id: int) -> tuple[bool, dict[str, Optional[str]]]:
        cursor.execute("""
            SELECT items.name, recipe.desc, recipe.meta
            FROM recipe
            LEFT JOIN items ON recipe.result_id = items.id
            WHERE recipe.item1_id = ? AND recipe.item2_id = ?
        """, (item1_id, item2_id))
        
        if row := cursor.fetchone():
            return True, {"result": row[0], "desc": row[1], "meta": row[2]}
        return False, {"result": None, "desc": None, "meta": None}
    
    def _is_tier_correlate(self, result_obj: ComboResult) -> bool:
        return (
            (result_obj.tier == 1 and result_obj.result in self.goal_elems) or 
            (result_obj.tier == 2 and result_obj.result in self.guide_elems) or 
            (result_obj.tier == 3 and result_obj.result not in self.goal_elems + self.guide_elems)
        )

    def _prompt_gemini(self, user_prompt: str) -> ComboResult:
        response = client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config={
                "system_instruction": self.system_prompt,
                "response_mime_type": "application/json",
                "response_schema": ComboResult
            }
        )
        result_obj: ComboResult = response.parsed # type: ignore
        return result_obj
    
    def _prompt_ollama(self, user_prompt: str) -> ComboResult:
        response = ollama.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            format=ComboResult.model_json_schema()
        )

        raw_content = response['message']['content']
        thought_match = re.search(r'<think>(.*?)</think>', raw_content, re.DOTALL)
        thought_process = thought_match.group(1).strip() if thought_match else "No thought process found."   
        print(thought_process + "\n")

        json_only = re.sub(r'<think>.*?</think>', '', raw_content, flags=re.DOTALL).strip()     
        return ComboResult.model_validate_json(json_only)
    
    @retry(
        wait=wait_exponential(multiplier=2, min=4, max=30), 
        stop=stop_after_attempt(10), 
        retry=retry_if_exception_type(ServerError)
    )
    def _prompt_genai(self, discovered: list[str], item1: str, item2: str) -> ComboResult:
        user_prompt = f"""Combine {item1} and {item2}
Context: Dscovered elements: 
{', '.join(discovered)}"""
        
        if self.provider == "gemini":
            result = self._prompt_gemini(user_prompt)
        else:
            result = self._prompt_ollama(user_prompt)

        return self._post_process(result)

    def _post_process(self, result_obj: ComboResult) -> ComboResult:
        if self._is_tier_correlate(result_obj):
            return result_obj
        
        print(f"AI claims {result_obj.result} as tier {result_obj.tier}")
        if result_obj.result and (canon := self._check_similar(result_obj.result)):
            result_obj.result = canon

        if self._is_tier_correlate(result_obj):
            return result_obj
        
        return ComboResult()

    def _check_similar(self, text: str):
        vec = get_embed_blob(text)
        query = "SELECT name, distance FROM item_embeds WHERE embed MATCH ? AND k = 20 ORDER BY distance ASC"
        
        with sqlite3.connect("combinations.db") as conn:
            load_sqlite_vec(conn)
            rows = conn.execute(query, (vec,)).fetchall()

        for item, dist in rows:
            if dist > 0:
                print(f'AI: "{text}" vs. Inventory: "{item}" --> distance = {dist}')
            if dist < MIN_DIST:
                return item
        return None

    def combine(self, discovered: list[str], item1: str, item2: str) -> dict[str, Optional[str]]:
        with sqlite3.connect("combinations.db") as conn:
            load_sqlite_vec(conn)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM items WHERE name = ?", (item1,))
            item1_id = cursor.fetchone()[0]

            cursor.execute("SELECT id FROM items WHERE name = ?", (item2,))
            item2_id = cursor.fetchone()[0]

            item1_id, item2_id = sorted((item1_id, item2_id))
            is_cached, result = self._try_combine(cursor, item1_id, item2_id)
            if is_cached:
                return result
            
            response = self._prompt_genai(discovered, item1, item2)
            result = response.result

            result_id = None
            if result:
                if canon := self._check_similar(result):
                    result = canon

                embed_and_store([result])
                cursor.execute("INSERT OR IGNORE INTO items (name) VALUES (?)", (result,))
                cursor.execute("SELECT id FROM items WHERE name = ?", (result,))
                result_id = cursor.fetchone()[0]

            cursor.execute(
                "INSERT OR IGNORE INTO recipe (item1_id, item2_id, result_id, desc, meta) VALUES (?, ?, ?, ?, ?)", 
                (item1_id, item2_id, result_id, response.desc, response.meta)
            )

        cursor.connection.commit()
        return {"result": result, "desc": response.desc, "meta": response.meta}

    def _get_recipe_results(self) -> list[str]:
        with sqlite3.connect("combinations.db") as conn:
            load_sqlite_vec(conn)
            return conn.execute("""
            SELECT items.name 
            FROM items 
            LEFT JOIN recipe ON recipe.result_id = items.id 
            WHERE recipe.item1_id IS NOT NULL""").fetchall()

