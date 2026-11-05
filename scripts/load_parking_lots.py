import os
from pathlib import Path

import boto3
import pandas as pd

TABLE_NAME = os.getenv("PARKING_TABLE", "k8s-lab-occupancy-status")
REGION = os.getenv("AWS_REGION", "eu-north-1")
CSV_FILE = os.getenv("PARKING_CSV", "Lisbon_parking4.csv")
CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / CSV_FILE


def main():
    df = pd.read_csv(CSV_PATH, sep=";")
    df["timestamp"] = pd.to_datetime(
        df["datetime"], format="mixed", dayfirst=True, errors="coerce"
    )

    df = (
        df.dropna(subset=["id_park", "timestamp", "occupancy", "max_capacity"])
        .drop_duplicates(subset=["id_park", "timestamp"])   # ключ id_park + ts должен быть уникальным
        .sort_values(["id_park", "timestamp"])
    )

    print(f"Writing {len(df)} records from {CSV_FILE} to {TABLE_NAME}...")

    table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE_NAME)

    with table.batch_writer(overwrite_by_pkeys=["id_park", "ts"]) as batch:
        for i, row in enumerate(df.itertuples(index=False), start=1):
            batch.put_item(
                Item={
                    "id_park": str(row.id_park),
                    "ts": row.timestamp.strftime("%Y-%m-%dT%H:%M:%S"),
                    "max_capacity": int(row.max_capacity),
                    "occupancy": int(row.occupancy),
                }
            )
            if i % 10_000 == 0:
                print(f"  {i} / {len(df)}")

    print(f"Loaded {len(df)} records for {df['id_park'].nunique()} parking lots")


if __name__ == "__main__":
    main()