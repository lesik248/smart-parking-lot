# smart-parking-lot

A machine learning service that predicts parking lot occupancy for a given parking lot and time.

## How it works

1. **Training.** `train_model.ipynb` trains a scikit-learn regression model on historical parking data from `data/raw/` and saves it in MLflow format to `model/`.
2. **Reference data.** Static parameters of each parking lot (capacity and coordinates) are stored in `seed/parking_lots.csv`. On startup, `init_db.py` loads them into a SQLite database.
3. **Serving.** A FastAPI app (`app/main.py`) loads the model and, for each request, builds features from the parking lot parameters and the requested timestamp: `max_capacity`, `hour`, `day_of_week`, `month`, `is_weekend`, `lon`, `lat`.

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/model-info` | Model path, features and MLflow metadata |
| `POST` | `/predict_occupancy` | Predicted occupancy for a parking lot at a given time |

Example request:

```bash
curl -X POST http://localhost:8000/predict_occupancy \
  -H "Content-Type: application/json" \
  -d '{"id_park": "<parking lot id>", "timestamp": "2026-10-24T18:00:00"}'
```

Interactive docs are available at `/docs`.

## Project structure

```
├── app/                  # FastAPI application
├── model/                # trained model (MLflow format)
├── seed/                 # parking lot parameters
├── data/raw/             # training data
├── train_model.ipynb     # model training
├── init_db.py            # loads seed data into SQLite
├── Dockerfile
├── docker-compose.yml    # local run with MLflow
└── infra/                # deployment to Kubernetes on AWS
```

## Run locally

```bash
docker build -t smart-parking-lot .
docker run -p 8000:8000 smart-parking-lot
```

Then open `http://localhost:8000/docs`.

## CI/CD

On every push to `dev`, GitHub Actions builds the Docker image and publishes it to GitHub Container Registry as `ghcr.io/lesik248/smart-parking-lot` with `latest` and commit SHA tags.

## Deployment

The service is deployed to a Kubernetes cluster on AWS provisioned with Terraform and Ansible, with MLflow backed by PostgreSQL and S3. See [`infra/README.md`](infra/README.md) for the architecture and instructions to deploy, stop, restart and destroy the infrastructure.