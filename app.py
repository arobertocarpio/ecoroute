from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
 
from src.routers.maps import router as maps_router
 
app = FastAPI(
    title="EcoRoute",
    description="Mayor distancia en menor tiempo",
    version="1.0.0",
)
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
 
app.include_router(maps_router)