FROM python:3.13-slim

WORKDIR /app

LABEL org.opencontainers.image.source="https://github.com/lesik248/smart-parking-lot"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PARKING_DB_PATH=/data/parking_lots.db
ENV MODEL_PATH=/app/model

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY model/ ./model/
COPY seed/ ./seed/
COPY init_db.py .

RUN mkdir -p /data

EXPOSE 8000

CMD ["sh", "-c", "python init_db.py && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]
