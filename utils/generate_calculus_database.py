import sqlite3
from datasets import load_dataset
import sys, os

DATASET_NAME = "nvidia/OpenMathReasoning"
SPLIT = "cot"
TARGET_SOURCE = "aops_c7_college_math"
N_ROWS = 500

DB_NAME = "calculus.db"
TABLE = "problems"

def main():
    ds = load_dataset(DATASET_NAME, split=SPLIT, streaming=True)

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expected_answer TEXT,
            problem_type TEXT,
            problem_source TEXT,
            generation_model TEXT,
            pass_rate_72b_tir TEXT,
            problem TEXT,
            generated_solution TEXT,
            inference_mode TEXT,
            used_in_kaggle INTEGER
        )
    """)
    cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE}_problem_source ON {TABLE}(problem_source)")
    conn.commit()

    # Remove old rows to keep db clean
    cur.execute(f"DELETE FROM {TABLE} WHERE problem_source = ?", (TARGET_SOURCE,))
    conn.commit()

    insert_sql = f"""
        INSERT INTO {TABLE} (
            expected_answer, problem_type, problem_source, generation_model, pass_rate_72b_tir,
            problem, generated_solution, inference_mode, used_in_kaggle
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    count = 0
    batch = []

    for ex in ds:
        if ex.get("problem_source") != TARGET_SOURCE:
            continue

        batch.append((
            ex.get("expected_answer"),
            ex.get("problem_type"),
            ex.get("problem_source"),
            ex.get("generation_model"),
            ex.get("pass_rate_72b_tir"),
            ex.get("problem"),
            ex.get("generated_solution"),
            ex.get("inference_mode"),
            1 if ex.get("used_in_kaggle") else 0,
        ))

        count += 1
        if len(batch) >= 50:
            cur.executemany(insert_sql, batch)
            conn.commit()
            batch.clear()

        if count >= N_ROWS:
            break

    if batch:
        cur.executemany(insert_sql, batch)
        conn.commit()

    cur.execute(f"SELECT COUNT(*) FROM {TABLE} WHERE problem_source = ?", (TARGET_SOURCE,))
    final_count = cur.fetchone()[0]
    conn.close()

    print(f"Rows in DB for {TARGET_SOURCE}: {final_count}")

    # IMPORTANT: avoid interpreter shutdown crash from background threads in streaming stack
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)

if __name__ == "__main__":
    main()
