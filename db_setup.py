import sqlite3

with open('data.csv', mode='r', encoding='utf-8-sig') as f:
    base_elems = [(x,) for x in f.readline().strip('\n').split(',') if x]
    target_elems = [(x,) for x in f.readline().strip('\n').split(',') if x]
    guide_elems = [(x,) for line in f.readlines() for x in line.strip('\n').split(',') if x]

conn = sqlite3.connect('combinations.db')
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
        FOREIGN KEY (item1_id) REFERENCES items(id)
        FOREIGN KEY (item2_id) REFERENCES items(id)
        FOREIGN KEY (result_id) REFERENCES items(id)
        PRIMARY KEY (item1_id, item2_id)
    );
""")

cursor.executemany("INSERT OR IGNORE INTO items (name, is_base) VALUES (?, TRUE)", base_elems)
cursor.executemany("INSERT OR IGNORE INTO items (name, is_goal) VALUES (?, TRUE)", target_elems)
cursor.executemany("INSERT OR IGNORE INTO items (name, is_guide) VALUES (?, TRUE)", guide_elems)

conn.commit()
conn.close()
