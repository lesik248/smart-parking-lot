import logging
import os
import time

import boto3
import psycopg
from boto3.dynamodb.conditions import Key
from prometheus_client import Counter, Gauge, start_http_server

DATABASE_URL = os.environ["DATABASE_URL"]
STATUS_TABLE = os.getenv("STATUS_TABLE", "k8s-lab-occupancy-status")
AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")
INTERVAL = int(os.getenv("EVAL_INTERVAL", "60"))
METRICS_PORT = int(os.getenv("METRICS_PORT", "8000"))
TS_FORMAT = "%Y-%m-%dT%H:%M:%S"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("evaluator")

# --- Prometheus metrics ---
MAE = Gauge("parking_model_mae", "Mean absolute error of evaluated predictions")
RMSE = Gauge("parking_model_rmse", "Root mean squared error of evaluated predictions")
BIAS = Gauge("parking_model_bias", "Mean error (predicted - actual); >0 means overestimation")
WITHIN_10 = Gauge("parking_model_within_10_ratio", "Share of predictions within 10 spaces of actual")
EVALUATED = Gauge("parking_model_evaluated_predictions", "Predictions matched with actual occupancy")

LOT_MAE = Gauge("parking_model_lot_mae", "MAE per parking lot", ["id_park"])
LOT_BIAS = Gauge("parking_model_lot_bias", "Mean error per parking lot", ["id_park"])
LOT_COUNT = Gauge("parking_model_lot_evaluated", "Evaluated predictions per parking lot", ["id_park"])

PENDING = Gauge("parking_evaluator_pending_predictions", "Batch predictions without a matching actual record")
LAST_SUCCESS = Gauge("parking_evaluator_last_success_timestamp_seconds", "Time of the last successful run")
RUN_ERRORS = Counter("parking_evaluator_run_errors_total", "Failed evaluation runs")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS prediction_errors (
    prediction_id       BIGINT PRIMARY KEY REFERENCES predictions(id) ON DELETE CASCADE,
    id_park             TEXT NOT NULL,
    target_ts           TIMESTAMP NOT NULL,
    predicted_occupancy DOUBLE PRECISION NOT NULL,
    actual_occupancy    INTEGER NOT NULL,
    max_capacity        INTEGER NOT NULL,
    error               DOUBLE PRECISION NOT NULL,
    evaluated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

PENDING_SQL = """
SELECT p.id, p.id_park, p.target_ts, p.predicted_occupancy
FROM predictions p
LEFT JOIN prediction_errors e ON e.prediction_id = p.id
WHERE p.source = 'batch' AND e.prediction_id IS NULL
"""


def query_all(table, **kwargs):
    items = []
    while True:
        response = table.query(**kwargs)
        items.extend(response["Items"])
        if "LastEvaluatedKey" not in response:
            return items
        kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]


def fetch_actuals(table, id_park, ts_from, ts_to):
    """Actual occupancy of one parking lot in [ts_from, ts_to], keyed by ts."""
    items = query_all(
        table,
        KeyConditionExpression=Key("id_park").eq(id_park) & Key("ts").between(ts_from, ts_to),
    )
    return {item["ts"]: (int(item["occupancy"]), int(item["max_capacity"])) for item in items}


def evaluate_pending(conn, table):
    """Match new predictions with actuals and store the errors. Returns (matched, unmatched)."""
    pending = conn.execute(PENDING_SQL).fetchall()
    if not pending:
        return 0, 0

    by_lot = {}
    for prediction_id, id_park, target_ts, predicted in pending:
        by_lot.setdefault(id_park, []).append((prediction_id, target_ts, predicted))

    matched = []
    for id_park, predictions in by_lot.items():
        ts_values = [target_ts.strftime(TS_FORMAT) for _, target_ts, _ in predictions]
        actuals = fetch_actuals(table, id_park, min(ts_values), max(ts_values))

        for (prediction_id, target_ts, predicted), ts in zip(predictions, ts_values):
            if ts in actuals:
                actual, capacity = actuals[ts]
                matched.append(
                    (prediction_id, id_park, target_ts, predicted, actual, capacity, predicted - actual)
                )

    if matched:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO prediction_errors
                    (prediction_id, id_park, target_ts, predicted_occupancy,
                     actual_occupancy, max_capacity, error)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (prediction_id) DO NOTHING
                """,
                matched,
            )

    return len(matched), len(pending) - len(matched)


def update_metrics(conn):
    count, mae, rmse, bias, within_10 = conn.execute(
        """
        SELECT count(*),
               avg(abs(error)),
               sqrt(avg(error * error)),
               avg(error),
               avg((abs(error) <= 10)::int)
        FROM prediction_errors
        """
    ).fetchone()

    EVALUATED.set(count)
    if count:
        MAE.set(float(mae))
        RMSE.set(float(rmse))
        BIAS.set(float(bias))
        WITHIN_10.set(float(within_10))

    rows = conn.execute(
        "SELECT id_park, count(*), avg(abs(error)), avg(error) FROM prediction_errors GROUP BY id_park"
    ).fetchall()
    for id_park, lot_count, lot_mae, lot_bias in rows:
        LOT_COUNT.labels(id_park).set(lot_count)
        LOT_MAE.labels(id_park).set(float(lot_mae))
        LOT_BIAS.labels(id_park).set(float(lot_bias))


def main():
    start_http_server(METRICS_PORT)
    log.info("Serving metrics on :%s/metrics", METRICS_PORT)

    table = boto3.resource("dynamodb", region_name=AWS_REGION).Table(STATUS_TABLE)

    while True:
        try:
            with psycopg.connect(DATABASE_URL, connect_timeout=5) as conn:
                conn.execute(SCHEMA_SQL)
                matched, unmatched = evaluate_pending(conn, table)
                update_metrics(conn)

            PENDING.set(unmatched)
            LAST_SUCCESS.set_to_current_time()
            log.info("Run finished: %s newly matched, %s without actuals", matched, unmatched)
        except Exception:
            RUN_ERRORS.inc()
            log.exception("Evaluation run failed")

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()