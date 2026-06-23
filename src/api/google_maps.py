import os
import googlemaps
 
from fastapi import HTTPException
from dotenv import load_dotenv
 
load_dotenv()
 
def get_gmaps() -> googlemaps.Client:
    key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="GOOGLE_MAPS_API_KEY no configurada en .env")
    return googlemaps.Client(key=key)
