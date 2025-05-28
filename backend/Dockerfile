# backend/Dockerfile
FROM python:3.12-slim

# 1. install OS deps (optional but nice for faster wheels)
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# 2. copy requirements & install
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. copy your FastAPI code
COPY . .

# 4. start the server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
