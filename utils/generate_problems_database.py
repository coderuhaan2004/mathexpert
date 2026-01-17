#!/usr/bin/env python3
import sqlite3
import json
from datasets import load_dataset, get_dataset_split_names

DATASET_NAME = "brando/olympiad-bench-imo-math-boxed-825-v2-21-08-2024"
DB_NAME = "olympiad.db"
TABLE = "problems"

def to_sqlite_value(x):
    if x is None:
        return None
    if isinstance(x, bool):
        return int(x)
    if isinstance(x, (int, float, str, bytes)):
        return x
    try:
        return json.dumps(x, ensure_ascii=False)
    except Exception:
        return str(x)

def ensure_fresh_table(cur: sqlite3.Cursor):
    # Drop old table so schema matches exactly
    cur.execute(f"DROP TABLE IF EXISTS {TABLE}")

    cur.execute(f"""
        CREATE TABLE {TABLE} (
            id INTEGER,
            subfield TEXT,
            context TEXT,
            problem TEXT,
            solution TEXT,
            final_answer_json TEXT,
            is_multiple_answer INTEGER,
            unit TEXT,
            answer_type TEXT,
            error TEXT,
            original_solution_json TEXT,
            split TEXT
        )
    """)

    # Indexes (safe now because columns exist)
    cur.execute(f"CREATE INDEX idx_{TABLE}_id ON {TABLE}(id)")
    cur.execute(f"CREATE INDEX idx_{TABLE}_subfield ON {TABLE}(subfield)")
    cur.execute(f"CREATE INDEX idx_{TABLE}_answer_type ON {TABLE}(answer_type)")
    cur.execute(f"CREATE INDEX idx_{TABLE}_split ON {TABLE}(split)")

def main():
    splits = get_dataset_split_names(DATASET_NAME) or ["train"]
    print("Splits:", splits)

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    ensure_fresh_table(cur)
    conn.commit()

    insert_sql = f"""
        INSERT INTO {TABLE} (
            id, subfield, context, problem, solution,
            final_answer_json, is_multiple_answer, unit,
            answer_type, error, original_solution_json, split
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    total = 0
    for split in splits:
        print(f"Loading split: {split}")
        ds = load_dataset(DATASET_NAME, split=split)

        batch = []
        for ex in ds:
            batch.append((
                to_sqlite_value(ex.get("id")),
                to_sqlite_value(ex.get("subfield")),
                to_sqlite_value(ex.get("context")),
                to_sqlite_value(ex.get("problem")),
                to_sqlite_value(ex.get("solution")),
                to_sqlite_value(ex.get("final_answer")),
                to_sqlite_value(ex.get("is_multiple_answer")),
                to_sqlite_value(ex.get("unit")),
                to_sqlite_value(ex.get("answer_type")),
                to_sqlite_value(ex.get("error")),
                to_sqlite_value(ex.get("original_solution")),
                split,
            ))

            if len(batch) >= 200:
                cur.executemany(insert_sql, batch)
                conn.commit()
                total += len(batch)
                batch.clear()

        if batch:
            cur.executemany(insert_sql, batch)
            conn.commit()
            total += len(batch)

        print(f"Inserted split {split}")

    conn.close()
    print(f"Done. Total rows inserted: {total}")
    print(f"Database saved as: {DB_NAME}")

if __name__ == "__main__":
    main()