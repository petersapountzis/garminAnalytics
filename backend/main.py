from fastapi import FastAPI, Query
from datetime import date
from sqlalchemy import create_engine, text
import os

PG_URL = (
    f"postgresql+psycopg://{os.getenv('PG_USER')}:{os.getenv('PG_PW')}"
    f"@timescaledb:5432/{os.getenv('PG_DB','garmin')}"
)
engine = create_engine(PG_URL, pool_pre_ping=True)
app = FastAPI(title="Garmin Analytics API")

@app.get("/daily", summary="Numeric daily metrics as rows")
def daily(
    field: str = Query("Steps", description="e.g. Steps, BodyBattery, HRV"),
    start: date = Query(...),
    end:   date = Query(...)
):
    sql = text("""
        SELECT
          date_trunc('day', time) AS day,
          avg(value::double precision) AS avg_val
        FROM raw_garmin
        WHERE field = :field
          AND value ~ '^[0-9.]+$'
          AND time BETWEEN :start AND (:end + interval '1 day')
        GROUP BY 1
        ORDER BY 1
    """)
    with engine.begin() as conn:
        rows = conn.execute(sql, {"field": field,
                                  "start": start,
                                  "end": end}).fetchall()
    return [{"day": r.day.isoformat(), "value": r.avg_val} for r in rows]

@app.get("/intraday", summary="Time-series for a single day")
def intraday(
    field: str = Query("HeartRateIntraday"),
    day:   date = Query(...)
):
    sql = text("""
      SELECT time, value
      FROM raw_garmin
      WHERE measurement = :field
        AND time::date = :day
        AND value ~ '^[0-9.]+$'
      ORDER BY time
    """)
    with engine.begin() as c:
        rows = c.execute(sql, {"field": field, "day": day}).fetchall()
    return [{"t": r.time.isoformat(), "v": float(r.value)} for r in rows]
