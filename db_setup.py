import numpy as np
import sqlite3

import ollama
import sqlite_vec


def get_embed_blob(text: str) -> bytes:
    response = ollama.embeddings(
        model="nomic-embed-text",
        prompt="search_query: " + text.lower().strip()
    )
    return np.array(response["embedding"], dtype=np.float32).tobytes()

def embed_and_store(texts: list[str]):
    embeds = [get_embed_blob(text) for text in texts]
    with sqlite3.connect('combinations.db') as conn:
        load_sqlite_vec(conn)
        conn.executemany("INSERT OR IGNORE INTO item_embeds(name, embed) VALUES (?, ?)", [tuple(p) for p in zip(texts, embeds)])
        conn.commit()

def load_sqlite_vec(conn: sqlite3.Connection):
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)

def get_elems():
    with open('data.csv', mode='r', encoding='utf-8-sig') as f:
        base_elems = [(x,) for x in f.readline().strip('\n').split(',') if x]
        goal_elems = [(x,) for x in f.readline().strip('\n').split(',') if x]
        guide_elems = [(x,) for line in f.readlines() for x in line.strip('\n').split(',') if x]
    return base_elems, goal_elems, guide_elems

def create_tables():
    base_elems, goal_elems, guide_elems = get_elems()

    with sqlite3.connect('combinations.db') as conn:
        load_sqlite_vec(conn)

        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                is_base INTEGER NOT NULL DEFAULT FALSE,
                is_goal INTEGER NOT NULL DEFAULT FALSE,
                is_guide INTEGER NOT NULL DEFAULT FALSE
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipe (
                item1_id INTEGER NOT NULL,
                item2_id INTEGER NOT NULL CHECK (item2_id >= item1_id),
                result_id INTEGER,
                desc TEXT,
                meta TEXT,
                FOREIGN KEY (item1_id) REFERENCES items(id)
                FOREIGN KEY (item2_id) REFERENCES items(id)
                FOREIGN KEY (result_id) REFERENCES items(id)
                PRIMARY KEY (item1_id, item2_id)
            );
        """)
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS item_embeds USING vec0(
                name TEXT,
                embed FLOAT[768] distance_metric=cosine
            );
        """)

        cursor.executemany("INSERT OR IGNORE INTO items (name, is_base) VALUES (?, TRUE)", base_elems)
        cursor.executemany("INSERT OR IGNORE INTO items (name, is_goal) VALUES (?, TRUE)", goal_elems)
        cursor.executemany("INSERT OR IGNORE INTO items (name, is_guide) VALUES (?, TRUE)", guide_elems)
        cursor.execute(
            "INSERT OR IGNORE INTO recipe (item1_id, item2_id, result_id, desc, meta) VALUES (?, ?, ?, ?, ?)", 
            (2, 4, 26, 
             "The commodification of territory through state or private investment yields extractable raw materials.", 
             "Natural Resources acts as a critical economic bridge. In a geopolitical game, this serves as the foundational prerequisite for unlocking 'Industry', 'Oil', 'Colonialism', and eventually the 'Petrodollar'."
             )
            )

    embed_and_store([x[0] for x in base_elems + goal_elems + guide_elems])


if __name__ == "__main__":
    create_tables()