from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
import sqlite3
import pickle
import pandas as pd
import holidays
import numpy as np

with open("model/parking-model.pkl", "rb") as f:
    model = pickle.load(f)


FEATURE_COLUMNS = [
    "max_capacity", "hour", "day_of_week", "month",
    "is_holiday", "is_weekend",
    "lon", "lat", "dist_to_center",
    "occupancy_mean", "occupancy_max",
    "occupancy_lag1", "occupancy_lag2",
    "occupancy_dayofweek_mean"
]

app = FastAPI(title="Parking API")

class CurrentRequest(BaseModel):
    id_park: str


class PredictRequest(BaseModel):
    id_park: str
    timestamp: datetime

def get_db_connection():
    return sqlite3.connect("data/parking_lots.db", detect_types=sqlite3.PARSE_DECLTYPES)

center_lat = 38.71340301220318
center_lon = -9.138537246528323


def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # km
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)

    a = np.sin(dphi/2)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))

def get_parking_parameters(id_park: str):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT max_capacity, lon, lat, occupancy_mean, occupancy_max
        FROM lot_parameters
        WHERE id = ?
    """, (id_park,))

    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    max_capacity, lon, lat, occ_mean, occ_max = row

    # compute distance dynamically
    dist_to_center = haversine(lat, lon, center_lat, center_lon)

    return {
        "max_capacity": max_capacity,
        "lon": lon,
        "lat": lat,
        "dist_to_center": dist_to_center,
        "occupancy_mean": occ_mean,
        "occupancy_max": occ_max
    }

def get_last_occupancies(id_park: str):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT occupancy
        FROM parking_data
        WHERE lot_id = ?
        ORDER BY timestamp DESC
        LIMIT 2
    """, (id_park,))

    rows = cursor.fetchall()
    conn.close()

    if len(rows) < 1:
        return None

    lag1 = rows[0][0]
    lag2 = rows[1][0] if len(rows) > 1 else lag1

    return {"lag1": lag1, "lag2": lag2}

@app.post("/current_occupancy")
def current_occupancy(req: CurrentRequest):

    lags = get_last_occupancies(req.id_park)
    if lags is None:
        return {"error": "No occupancy data for this parking lot"}

    return {
        "id_park": req.id_park,
        "current_occupancy": lags["lag1"]
    }

@app.post("/predict_occupancy")
def predict_occupancy(req: PredictRequest):

    params = get_parking_parameters(req.id_park)
    if params is None:
        return {"error": "Unknown parking id"}

    lags = get_last_occupancies(req.id_park)
    if lags is None:
        return {"error": "Not enough occupancy history for prediction"}

    ts = req.timestamp
    hour = ts.hour
    dow = ts.weekday()
    month = ts.month

    pt_holidays = holidays.Portugal()
    is_holiday = int(ts.date() in pt_holidays)
    is_weekend = int(dow >= 5)

    features = {
        "max_capacity": params["max_capacity"],
        "hour": hour,
        "day_of_week": dow,
        "month": month,
        "is_holiday": is_holiday,
        "is_weekend": is_weekend,
        "lon": params["lon"],
        "lat": params["lat"],
        "dist_to_center": params["dist_to_center"],  # computed!
        "occupancy_mean": params["occupancy_mean"],
        "occupancy_max": params["occupancy_max"],
        "occupancy_lag1": lags["lag1"],
        "occupancy_lag2": lags["lag2"],
        "occupancy_dayofweek_mean": params["occupancy_mean"],
    }

    df = pd.DataFrame([features])[FEATURE_COLUMNS]
    pred = model.predict(df)[0]

    return {
        "id_park": req.id_park,
        "timestamp": req.timestamp,
        "predicted_occupancy": round(float(pred), 2)
    }
