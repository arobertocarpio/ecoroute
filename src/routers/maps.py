import re
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from src.api.google_maps import get_gmaps
from src.schemas.schema_google_maps import RouteRequest, MatrixRequest

router = APIRouter()

TRAFFIC_LEVELS = [
    (1.1, "Fluido"),
    (1.3, "Moderado"),
    (1.6, "Lento"),
    (float("inf"), "Muy lento / Congestionado"),
]

def classify_traffic(normal: float, with_traffic: float) -> str:
    ratio = with_traffic / normal if normal > 0 else 1
    return next(label for threshold, label in TRAFFIC_LEVELS if ratio < threshold)

def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)

def check_element(element: dict, context: str = "ruta"):
    if element.get("status") != "OK":
        raise HTTPException(
            status_code=404,
            detail=f"No se encontró {context}: {element.get('status')}"
        )


@router.get("/", tags=["Info"])
def root():
    return {
        "name": "EcoRoute API",
        "docs": "/docs",
        "endpoints": ["/distance", "/traffic", "/route", "/matrix"]
    }


@router.get("/distance", tags=["Distancia"])
def distance(
    origin: str = Query(..., examples=["Ciudad de México"]),
    destination: str = Query(..., examples=["Guadalajara, México"]),
    mode: str = Query("driving", description="driving | walking | bicycling | transit")
):
    """Distancia y tiempo estimado entre dos puntos."""
    gmaps = get_gmaps()
    result = gmaps.distance_matrix(
        origins=[origin],
        destinations=[destination],
        mode=mode,
        language="es"
    )
    element = result["rows"][0]["elements"][0]
    check_element(element)

    return {
        "origin":        result["origin_addresses"][0],
        "destination":   result["destination_addresses"][0],
        "mode":          mode,
        "distance_km":   round(element["distance"]["value"] / 1000, 2),
        "distance_text": element["distance"]["text"],
        "duration_min":  round(element["duration"]["value"] / 60, 1),
        "duration_text": element["duration"]["text"],
    }


@router.get("/traffic", tags=["Tráfico"])
def traffic(
    origin: str = Query(..., examples=["Reforma, CDMX"]),
    destination: str = Query(..., examples=["Aeropuerto AICM, CDMX"]),
    model: str = Query("best_guess", description="best_guess | pessimistic | optimistic")
):
    """Tiempo de viaje con tráfico en tiempo real y nivel de congestión."""
    gmaps = get_gmaps()
    result = gmaps.distance_matrix(
        origins=[origin],
        destinations=[destination],
        mode="driving",
        departure_time=datetime.now(),
        traffic_model=model,
        language="es"
    )
    element = result["rows"][0]["elements"][0]
    check_element(element, "ruta con tráfico")

    normal_s  = element["duration"]["value"]
    traffic_s = element.get("duration_in_traffic", element["duration"])["value"]
    normal_min  = round(normal_s / 60, 1)
    traffic_min = round(traffic_s / 60, 1)

    return {
        "origin":               result["origin_addresses"][0],
        "destination":          result["destination_addresses"][0],
        "distance_km":          round(element["distance"]["value"] / 1000, 2),
        "distance_text":        element["distance"]["text"],
        "duration_normal_min":  normal_min,
        "duration_traffic_min": traffic_min,
        "delay_min":            round(traffic_min - normal_min, 1),
        "traffic_level":        classify_traffic(normal_min, traffic_min),
        "traffic_model":        model,
        "checked_at":           datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@router.post("/route", tags=["Rutas"])
def optimal_route(body: RouteRequest):
    """Ruta óptima entre dos puntos con paradas opcionales."""
    gmaps = get_gmaps()

    kwargs = dict(
        origin=body.origin,
        destination=body.destination,
        mode="driving",
        departure_time=datetime.now(),
        traffic_model="best_guess",
        optimize_waypoints=True,
        language="es"
    )
    if body.waypoints:
        kwargs["waypoints"] = body.waypoints
    if body.avoid:
        kwargs["avoid"] = body.avoid

    directions = gmaps.directions(**kwargs)
    if not directions:
        raise HTTPException(status_code=404, detail="No se encontró ninguna ruta")

    route = directions[0]
    legs  = route["legs"]
    total_m = sum(leg["distance"]["value"] for leg in legs)
    total_s = sum(leg["duration"]["value"] for leg in legs)

    return {
        "summary":             route.get("summary", "Ruta principal"),
        "total_distance_km":   round(total_m / 1000, 2),
        "total_distance_text": f"{total_m / 1000:.1f} km",
        "total_duration_min":  round(total_s / 60, 1),
        "total_duration_text": f"{total_s // 3600}h {(total_s % 3600) // 60}min",
        "waypoints_order":     route.get("waypoint_order", []),
        "legs": [
            {
                "leg":          i + 1,
                "from":         leg["start_address"],
                "to":           leg["end_address"],
                "distance_km":  round(leg["distance"]["value"] / 1000, 2),
                "duration_min": round(leg["duration"]["value"] / 60, 1),
            }
            for i, leg in enumerate(legs)
        ],
        "steps_first_leg": [
            {
                "instruction": strip_html(step["html_instructions"]),
                "distance":    step["distance"]["text"],
                "duration":    step["duration"]["text"],
            }
            for step in legs[0]["steps"]
        ],
    }


@router.post("/matrix", tags=["Matriz"])
def distance_matrix(body: MatrixRequest):
    """Matriz de distancias para múltiples orígenes y destinos en una sola llamada."""
    gmaps = get_gmaps()

    kwargs = dict(
        origins=body.origins,
        destinations=body.destinations,
        mode="driving",
        language="es"
    )
    if body.with_traffic:
        kwargs["departure_time"] = datetime.now()
        kwargs["traffic_model"]  = "best_guess"

    result = gmaps.distance_matrix(**kwargs)

    rows = []
    for i, row in enumerate(result["rows"]):
        for j, element in enumerate(row["elements"]):
            entry = {
                "origin":      result["origin_addresses"][i],
                "destination": result["destination_addresses"][j],
            }
            if element["status"] == "OK":
                entry["distance_km"]   = round(element["distance"]["value"] / 1000, 2)
                entry["distance_text"] = element["distance"]["text"]
                entry["duration_min"]  = round(element["duration"]["value"] / 60, 1)
                entry["duration_text"] = element["duration"]["text"]
                if body.with_traffic and "duration_in_traffic" in element:
                    traffic_min = round(element["duration_in_traffic"]["value"] / 60, 1)
                    normal_min  = entry["duration_min"]
                    entry["duration_traffic_min"] = traffic_min
                    entry["delay_min"]            = round(traffic_min - normal_min, 1)
                    entry["traffic_level"]        = classify_traffic(normal_min, traffic_min)
            else:
                entry["error"] = element["status"]
            rows.append(entry)

    return {
        "origins":      result["origin_addresses"],
        "destinations": result["destination_addresses"],
        "with_traffic": body.with_traffic,
        "results":      rows,
    }