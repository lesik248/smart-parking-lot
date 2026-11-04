import csv
import os
from decimal import Decimal
from pathlib import Path

import boto3

TABLE_NAME = os.getenv("PARKING_TABLE", "k8s-lab-parking-lots")
REGION = os.getenv("AWS_REGION", "eu-north-1")
SEED_PATH = Path(__file__).resolve().parent.parent / "seed" / "parking_lots.csv"

REQUIRED = ["id_park", "max_capacity", "lon", "lat"]


def main():
    with SEED_PATH.open(newline="") as f:
        rows = list(csv.DictReader(f))

    missing = set(REQUIRED) - set(rows[0].keys())
    if missing:
        raise ValueError(f"Missing columns in CSV: {missing}")

    table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE_NAME)

    with table.batch_writer(overwrite_by_pkeys=["id_park"]) as batch:
        for row in rows:
            batch.put_item(
                Item={
                    "id_park": row["id_park"],
                    "max_capacity": Decimal(row["max_capacity"]),
                    "lon": Decimal(row["lon"]),
                    "lat": Decimal(row["lat"]),
                }
            )

    print(f"Loaded {len(rows)} parking lots into {TABLE_NAME}")


if __name__ == "__main__":
    main()