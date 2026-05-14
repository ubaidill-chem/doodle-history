import sqlite3

from google import genai
import numpy as np
from pydantic import BaseModel, Field

from ai_engine import _check_similar
from db_setup import embed_and_store, load_sqlite_vec

class Candidate(BaseModel):
    result: str = Field(description="item name verbatim if from universe, otherwise 1-3 word novel concept in title case")
    desc: str = Field(description="max 15 words, punchy causal connection written for the player")
    reasoning: str = Field(description="one sentence, cites the specific causal or thematic mechanism and why this candidate ranks above the next")

class PairResult(BaseModel):
    item1: str
    item2: str
    candidates: list[Candidate] = Field(default_factory=list)

class BatchResult(BaseModel):
    results: list[PairResult]
    
SYSTEM_PROMPT = """You are an expert historian designing a discovery game about 20th century history. The game models history through the interaction of material conditions, economics, and power structures.

## Universe
{universe}

## Combination logic
For any set of two input items, identify 0, 1, 2, or 3 historically valid results, ranked by preference.

Candidate rules:
- Each candidate must be a universe item or a novel 1-3 word historical concept
- A novel concept is only valid if a direct causal link exists and it is not already implied by an existing universe item
- Each candidate must be distinct — no near-synonyms across the three slots
- Causal links must be direct. No chronological leaps. 
  e.g. Abstract or broad concepts like "Rocketry" and "Fuel" can NOT yield a specific event like "Apollo 11" without an intermediate term like "Space Race" being involved
- If fewer than 3 valid candidates exist, return only those that are valid
- If no valid result exists, return an empty candidates array

## Output format
JSON only. No explanation outside the JSON object.
{{
  "results": [
    {{
      "item1": str,
      "item2": str,
      "candidates": [{{"result": str, "desc": str, "reasoning": str}}]
    }}
  ]
}}

Empty candidates array if no valid result exists."""

CLIENT = genai.Client()

CHUNK_SIZE = 20

# def generate_cache(universe: list[str]):
#     sys_prompt = SYSTEM_PROMPT.format(universe=", ".join(universe))
    
#     return CLIENT.caches.create(
#     model="gemini-2.5-flash",
#     config=genai.types.CreateCachedContentConfig(
#         system_instruction=sys_prompt,
#     )
# )


def generate_candidates(universe: list[str], pairs: list[tuple[str, str]]) -> BatchResult:
    response = CLIENT.models.generate_content(
        model="gemini-3-flash-preview",
        contents="Combine:\n" + "\n".join(["+".join(pair) for pair in pairs]),
        config=genai.types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=BatchResult,
            system_instruction=SYSTEM_PROMPT.format(universe=", ".join(universe))
        )
    )
    res: BatchResult = response.parsed # type: ignore
    return res or BatchResult(results=[])


def store_result(conn: sqlite3.Connection, item_a: str, item_b: str, res: PairResult):
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM items WHERE name = ?", (item_a,))
    item1_id = cursor.fetchone()[0]

    cursor.execute("SELECT id FROM items WHERE name = ?", (item_b,))
    item2_id = cursor.fetchone()[0]

    item1_id, item2_id = sorted((item1_id, item2_id))

    if not res.candidates:
        cursor.execute(
            "INSERT OR IGNORE INTO candidate_recipe (item1_id, item2_id, result_id, desc, reasoning, rank) VALUES (?, ?, ?, ?, ?, ?)", 
            (item1_id, item2_id, None, None, None, 0)
        )
        return

    for i, candidate in enumerate(res.candidates):
        result = candidate.result
        if canon := _check_similar(result):
            result = canon

        embed_and_store(conn, result)
        cursor.execute("INSERT OR IGNORE INTO items (name) VALUES (?)", (result,))
        cursor.execute("SELECT id FROM items WHERE name = ?", (result,))
        result_id = cursor.fetchone()[0]

        cursor.execute(
            "INSERT OR IGNORE INTO candidate_recipe (item1_id, item2_id, result_id, desc, reasoning, rank) VALUES (?, ?, ?, ?, ?, ?)", 
            (item1_id, item2_id, result_id, candidate.desc, candidate.reasoning, i)
        )

        conn.commit()


def sort_by_sim(conn: sqlite3.Connection):
    cursor = conn.cursor()
    rows = cursor.execute("SELECT name, embed FROM item_embeds").fetchall()
    names = np.array([x[0] for x in rows])
    embed_mat = np.stack([np.frombuffer(x[1], dtype=np.float32) for x in rows])
    sim_mat = embed_mat @ embed_mat.T
    iu = np.triu_indices(sim_mat.shape[0])

    sim_values = sim_mat[iu]
    sort_indices = np.argsort(sim_values)[::-1]
    return list(zip(names[iu[0]][sort_indices], names[iu[1]][sort_indices]))


if __name__ == "__main__":
    with open('data.csv', mode='r', encoding='utf-8-sig') as f:
        items = [x for line in f.readlines() for x in line.strip('\n').split(',') if x]

    with sqlite3.connect("combinations.db") as conn:
        load_sqlite_vec(conn)
        existing_pairs = conn.execute(
            """
            SELECT item1.name, item2.name 
            FROM candidate_recipe cr 
            JOIN items item1 ON cr.item1_id = item1.id JOIN items item2 ON cr.item2_id = item2.id"""
        ).fetchall()

        pairs = [pair for pair in sort_by_sim(conn) if pair not in existing_pairs]

        for i in range(0, len(pairs), CHUNK_SIZE):
            batch_res = generate_candidates(items, pairs[i:i + CHUNK_SIZE])
            for res in batch_res.results:
                print(res.item1, "+", res.item2, "=", " OR ".join([x.result for x in res.candidates]))
                store_result(conn, res.item1, res.item2, res)
