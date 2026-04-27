import sqlite3
from typing import Optional

from google import genai
from pydantic import BaseModel, Field


conn = sqlite3.connect("combinations.db")
cursor = conn.cursor()

cursor.execute("SELECT name FROM items WHERE is_goal = TRUE")
target_elems = [x[0] for x in cursor.fetchall()]

cursor.execute("SELECT name FROM items WHERE is_guide = TRUE")
guide_elems = [x[0] for x in cursor.fetchall()]

client = genai.Client()

system_prompt = f"""System: You are an expert historian running a 20th-century logic game. The user will combine two concepts Input A and Input B.
Milestone Targets: {target_elems}
Available Items: {guide_elems}

Rules:
1. Determine if combining Input A and Input B results in a historically accurate event, concept, or invention.
2. If there is NO historical or logical connection, you must return null.
3. If there is a connection, look at the Milestone Targets. If the result logically matches or heavily aligns with a target, you MUST output the exact name of that target.
4. If a valid historical result exists but does NOT trigger a Milestone, look at the Available Items. If it strongly aligns with an item in that list, output that exact name of that item.
5. If a valid historical result exists but does NOT match any available items, output a short, accurate 1-3 word name for the new concept.
6. If a valid historical result exists, also return a one sentence description or justification of why that result was choosen.

Output format: JSON only. {{"result": "Output Name", "desc": "Description or justification"}} or {{"result": null, "desc": null}}"""


class CombResult(BaseModel):
    result: Optional[str] = None
    desc: Optional[str] = Field(description="One sentence of description or justification of the combination result")


def _try_combine(item1_id: int, item2_id: int) -> Optional[tuple[Optional[str]]]:
    cursor.execute("""
        SELECT items.name 
        FROM recipe 
        JOIN items ON recipe.result_id = items.id
        WHERE recipe.item1_id = ? AND recipe.item2_id = ?
    """, (item1_id, item2_id))
    
    return cursor.fetchone()


def _prompt_genai(item1: str, item2: str) -> CombResult:
    user_prompt = f"Combine {item1} and {item2}"
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=user_prompt,
        config={
            "system_instruction": system_prompt,
            "response_mime_type": "application/json",
            "response_schema": CombResult
        }
    )
    return response.parsed # type: ignore


def combine(item1: str, item2: str) -> Optional[str]:
    cursor.execute("SELECT id FROM items WHERE name = ?", (item1,))
    item1_id = cursor.fetchone()[0]

    cursor.execute("SELECT id FROM items WHERE name = ?", (item2,))
    item2_id = cursor.fetchone()[0]

    item1_id, item2_id = sorted((item1_id, item2_id))
    if result := _try_combine(item1_id, item2_id):
        return result[0]
    
    result_obj = _prompt_genai(item1, item2)

    result = result_obj.result
    cursor.execute("INSERT OR IGNORE INTO items (name) VALUES (?)", (result,))
    cursor.execute("SELECT id FROM items WHERE name = ?", (result,))
    result_id = cursor.fetchone()[0]

    cursor.execute("INSERT OR IGNORE INTO recipe (item1_id, item2_id, result_id, desc) VALUES (?, ?, ?, ?)", 
                   (item1_id, item2_id, result_id, result_obj.desc))
    return result
