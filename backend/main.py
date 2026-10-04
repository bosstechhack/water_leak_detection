from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routers import network_api, analysis_api

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Water Leak Detection API")

# Allow CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(network_api.router, prefix="/api")
app.include_router(analysis_api.router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "Water Leak Detection API is running"}
