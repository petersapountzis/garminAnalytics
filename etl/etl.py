import os, time, datetime, warnings, pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, TEXT, DOUBLE_PRECISION
from influxdb import InfluxDBClient

warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# ---------- ENV ----------
INFLUX = dict(
    host=os.getenv("INFLUX_HOST", "influxdb"),
    port=int(os.getenv("INFLUX_PORT", 8086)),
    username=os.getenv("INFLUX_USER"),
    password=os.getenv("INFLUX_PW"),
    database=os.getenv("INFLUX_DB", "GarminStats"),
    timeout=15,
)
PG_URL = (
    f"postgresql+psycopg://{os.getenv('PG_USER')}:{os.getenv('PG_PW')}"
    f"@{os.getenv('PG_HOST', 'timescaledb')}:5432/{os.getenv('PG_DB', 'garmin')}"
)
LOOP = int(os.getenv("LOOP_SECONDS", 300))

# ---------- TARGET ENGINE ----------
engine = create_engine(PG_URL, pool_pre_ping=True)

with engine.begin() as conn:
    conn.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS raw_garmin (
            time TIMESTAMPTZ,
            measurement TEXT,
            field TEXT,
            value TEXT             
        );
        """
    )
    conn.execute(
        text("SELECT create_hypertable('raw_garmin','time', if_not_exists => TRUE);")
    )

# ---------- SOURCE ----------
influx = InfluxDBClient(**INFLUX)
QUERY = 'SELECT * FROM /.*/ WHERE time > now() - 24h'   # wide window during back-fill

# ---------- LOOP ----------
while True:
    result = influx.query(QUERY)

    frames = []
    for (meas, _), series in result.items():          # series is a generator
        rows = list(series)
        if not rows:
            continue
        df = pd.DataFrame(rows)
        df["measurement"] = meas
        frames.append(df)

    if frames:
        tidy = (
            pd.concat(frames)
              .melt(id_vars=["time", "measurement"],
                    var_name="field", value_name="value")
              .dropna(subset=["value"])
              [["time", "measurement", "field", "value"]]
        )

        # ---- FIX: ensure correct dtypes ----
        tidy["time"] = pd.to_datetime(tidy["time"], utc=True)

        tidy.to_sql(
    "raw_garmin",
    engine,
    if_exists="append",
    index=False,
    chunksize=10_000,
    dtype={
        "time": TIMESTAMP(timezone=True),
        "measurement": TEXT(),
        "field": TEXT(),
        "value": TEXT(),       # ← changed
    },
)
        print(f"[{datetime.datetime.utcnow().isoformat()}] wrote {len(tidy):,} rows")

    time.sleep(LOOP)
