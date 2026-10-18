from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import catalog
from database import Base, SessionLocal, engine
from routers import analysis_api, network_api

# Create database tables and copy the scenario catalog into SQLite
Base.metadata.create_all(bind=engine)
with SessionLocal() as session:
    catalog.sync(session)

app = FastAPI(title="Water Leak Localization System API")

# Allow CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(network_api.router, prefix="/api")
app.include_router(analysis_api.router, prefix="/api")


@app.get("/")
def read_root():
    return {"message": "LeakLens Water Leak Localization System API is running"}
