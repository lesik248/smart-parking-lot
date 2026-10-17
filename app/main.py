import os
import sqlite3
from datetime import datetime
from pathlib import Path

import mlflow
import mlflow.sklearn
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

DB_PATH = Path(
    os.getenv("PARKING_DB_PATH", str(PROJECT_ROOT / "data" / "parking_lots.db"))
)

MODEL_PATH = Path(
    os.getenv("MODEL_PATH", str(PROJECT_ROOT / "model"))
)

model = mlflow.sklearn.load_model(str(MODEL_PATH))
FEATURE_COLUMNS = list(model.feature_names_in_)

try:
    _info = mlflow.models.get_model_info(str(MODEL_PATH))
    MODEL_METADATA = {
        "model_uuid": getattr(_info, "model_uuid", None),
        "mlflow_version": getattr(_info, "mlflow_version", None),
        "created_utc": getattr(_info, "utc_time_created", None),
    }
except Exception:
    MODEL_METADATA = {}

# The exact features used to train the model.
EXPECTED_FEATURES = [
    "max_capacity",
    "hour",
    "day_of_week",
    "month",
    "is_weekend",
    "lon",
    "lat",
]

if not hasattr(model, "feature_names_in_"):
    raise RuntimeError(
        "The registered model does not contain feature_names_in_. "
        "Retrain and register the model using a pandas DataFrame."
    )

FEATURE_COLUMNS = list(model.feature_names_in_)

if set(FEATURE_COLUMNS) != set(EXPECTED_FEATURES):
    raise RuntimeError(
        "The registered model uses unexpected features.\n"
        f"Expected: {EXPECTED_FEATURES}\n"
        f"Found: {FEATURE_COLUMNS}"
    )


# --------------------------------------------------
# FastAPI
# --------------------------------------------------

app = FastAPI(
    title="Parking Occupancy Prediction API",
    description="Predict parking occupancy using an MLflow model.",
    version="1.0.0",
)


class PredictRequest(BaseModel):
    id_park: str
    timestamp: datetime


# --------------------------------------------------
# Database
# --------------------------------------------------

def get_parking_parameters(id_park: str):
    """Get static characteristics of a parking lot."""

    if not DB_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Parking database not found: {DB_PATH}",
        )

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row

            row = conn.execute(
                """
                SELECT max_capacity, lon, lat
                FROM lot_parameters
                WHERE id = ?
                """,
                (id_park,),
            ).fetchone()

    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Could not read parking database: {exc}",
        ) from exc

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown parking ID: {id_park}",
        )

    params = dict(row)

    if any(params[column] is None for column in (
        "max_capacity", "lon", "lat"
    )):
        raise HTTPException(
            status_code=500,
            detail=f"Missing parking parameters for {id_park}",
        )

    return params


# --------------------------------------------------
# Health and model information
# --------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/model-info")
def model_info():
    return {
        "model_path": str(MODEL_PATH),
        "features": FEATURE_COLUMNS,
        **MODEL_METADATA,
    }


# --------------------------------------------------
# Prediction
# --------------------------------------------------

@app.post("/predict_occupancy")
def predict_occupancy(req: PredictRequest):
    """Predict occupancy for a parking lot at a given time."""

    params = get_parking_parameters(req.id_park)
    ts = req.timestamp

    # Create exactly the same features as during training.
    features = {
        "max_capacity": params["max_capacity"],
        "hour": ts.hour,
        "day_of_week": ts.weekday(),
        "month": ts.month,
        "is_weekend": int(ts.weekday() >= 5),
        "lon": params["lon"],
        "lat": params["lat"],
    }

    # Keep the exact feature order expected by the registered model.
    X = pd.DataFrame(
        [[features[column] for column in FEATURE_COLUMNS]],
        columns=FEATURE_COLUMNS,
    )

    prediction = float(model.predict(X)[0])

    return {
        "id_park": req.id_park,
        "timestamp": ts.isoformat(),
        "predicted_occupancy": round(prediction, 2),
    }