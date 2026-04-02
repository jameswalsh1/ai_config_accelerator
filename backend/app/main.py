from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import generate, wizard

app = FastAPI(title="AI Accelerator API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(wizard.router)
app.include_router(generate.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
