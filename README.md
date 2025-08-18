# MathOps Microservice

A lightweight python microservice that supports three math operations: power, fibonacci, and factorial.

## Tech stack
- Python 3.11 lite
  - FastAPI async API
  - Async worker queue
  - SQLite logging
  - Pydantic for serialization
- Docker-ready

## Build and run
```cmd
docker build -t mathops .

for cmd use:
docker run -p 8000:8000 -v "%cd%\db:/app/db" mathops

for powershell use:
docker run -p 8000:8000 -v "C:\Users\tudor\source\repos\PythonMath\db:/app/db" mathops
```

## API Example
```
POST /calculate
{
  "op": "pow",
  "a": 2,
  "b": 10
}

GET /result/{job_id}
```

## Interact with the web UI
Visit [http://localhost:8000/ui](http://localhost:8000/ui) to use the form-based interface.