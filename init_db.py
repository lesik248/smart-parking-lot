import os
import sqlite3
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent

SEED_PATH = BASE_DIR / "seed" / "parking_lots.csv"
DB_PATH = Path(
    os.getenv("PARKING_DB_PATH", str(BASE_DIR / "data" / "parking_lots.db"))
)

DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def init_db():
    if not SEED_PATH.exists():
        raise FileNotFoundError(f"Seed file not found: {SEED_PATH}")

    df = pd.read_csv(SEED_PATH)

    required = ["id_park", "max_capacity", "lon", "lat"]
    missing = set(required) - set(df.columns)

    if missing:
        raise ValueError(f"Missing columns in CSV: {missing}")

    df = df[required].copy()
    df["id_park"] = df["id_park"].astype(str)

    if df.isnull().any().any():
        raise ValueError("Seed CSV contains missing values")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lot_parameters (
                id TEXT PRIMARY KEY,
                max_capacity REAL NOT NULL,
                lon REAL NOT NULL,
                lat REAL NOT NULL
            )
        """)

        conn.executemany("""
            INSERT INTO lot_parameters (id, max_capacity, lon, lat)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                max_capacity = excluded.max_capacity,
                lon = excluded.lon,
                lat = excluded.lat
        """, [
            (
                row.id_park,
                float(row.max_capacity),
                float(row.lon),
                float(row.lat),
            )
            for row in df.itertuples(index=False)
        ])

    print(f"Database initialized: {DB_PATH}")
    print(f"Parking lots loaded: {len(df)}")


if __name__ == "__main__":
    init_db()