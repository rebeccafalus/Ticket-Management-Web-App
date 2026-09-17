from fastapi import FastAPI

app = FastAPI(title="Ticket Management ML Service")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}