import os
from datetime import datetime, timedelta
from pathlib import Path

import boto3
import mlflow
import mlflow.sklearn
import pandas as pd
import psycopg
from boto3.dynamodb.conditions import Key

MODEL_PATH = os.getenv("MODEL_PATH", "/app/model")
DATABASE_URL = os.environ["DATABASE_URL"]
STATUS_TABLE = os.getenv("STATUS_TABLE", "k8s-lab-occupancy-status")
AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")
DAYS = int(os.getenv("DAYS", "7"))
SEED_PATH = Path(__file__).resolve().parent.parent / "seed" / "parking_lots.csv"
TS_FORMAT = "%Y-%m-%dT%H:%M:%S"

SCHEMA_SQL = [
    """
    CREATE TABLE IF NOT EXISTS predictions (
        id                  BIGSERIAL PRIMARY KEY,
        created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
        id_park             TEXT NOT NULL,
        target_ts           TIMESTAMP NOT NULL,
        predicted_occupancy DOUBLE PRECISION NOT NULL,
        model_uuid          TEXT
    )
    """,
    "ALTER TABLE predictions ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'api'",
    """
    CREATE UNIQUE INDEX IF NOT EXISTS predictions_batch_unique
        ON predictions (id_park, target_ts) WHERE source = 'batch'
    """,
]


def query_all(table, **kwargs):
    """DynamoDB returns at most 1 MB per call, so follow LastEvaluatedKey."""
    items = []
    while True:
        response = table.query(**kwargs)
        items.extend(response["Items"])
        if "LastEvaluatedKey" not in response:
            return items
        kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]


def load_actuals(table, id_park):
    """Records of the last DAYS days of data for one parking lot."""
    latest = table.query(
        KeyConditionExpression=Key("id_park").eq(id_park),
        ScanIndexForward=False,
        Limit=1,
    )["Items"]
    if not latest:
        return []

    end = datetime.strptime(latest[0]["ts"], TS_FORMAT)
    start = (end - timedelta(days=DAYS)).strftime(TS_FORMAT)

    return query_all(
        table,
        KeyConditionExpression=Key("id_park").eq(id_park) & Key("ts").gte(start),
    )


def main():
    model = mlflow.sklearn.load_model(MODEL_PATH)
    features = list(model.feature_names_in_)
    model_uuid = getattr(mlflow.models.get_model_info(MODEL_PATH), "model_uuid", None)

    lots = pd.read_csv(SEED_PATH, dtype={"id_park": str})
    table = boto3.resource("dynamodb", region_name=AWS_REGION).Table(STATUS_TABLE)

    rows = []
    for lot in lots.itertuples(index=False):
        for item in load_actuals(table, lot.id_park):
            rows.append({
                "id_park": lot.id_park,
                "target_ts": datetime.strptime(item["ts"], TS_FORMAT),
                "max_capacity": float(item["max_capacity"]),
                "lon": float(lot.lon),
                "lat": float(lot.lat),
            })
        print(f"{lot.id_park}: {sum(r['id_park'] == lot.id_park for r in rows)} records")

    if not rows:
        print("No actuals found in DynamoDB, nothing to predict")
        return

    df = pd.DataFrame(rows)
    df["hour"] = df["target_ts"].dt.hour
    df["day_of_week"] = df["target_ts"].dt.dayofweek
    df["month"] = df["target_ts"].dt.month
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

    # One vectorized call for all rows instead of one request per row.
    df["predicted"] = model.predict(df[features])

    with psycopg.connect(DATABASE_URL) as conn:
        for sql in SCHEMA_SQL:
            conn.execute(sql)

        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO predictions (id_park, target_ts, predicted_occupancy, model_uuid, source)
                VALUES (%s, %s, %s, %s, 'batch')
                ON CONFLICT (id_park, target_ts) WHERE source = 'batch' DO NOTHING
                """,
                [
                    (r.id_park, r.target_ts.to_pydatetime(), float(r.predicted), model_uuid)
                    for r in df.itertuples(index=False)
                ],
            )

    print(f"Done: {len(df)} batch predictions for {df['id_park'].nunique()} parking lots")


if __name__ == "__main__":
    main()