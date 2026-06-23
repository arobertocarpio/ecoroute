from pydantic import BaseModel, Field
 
 
class RouteRequest(BaseModel):
    origin: str = Field(..., json_schema_extra={"example": "Ciudad de México"})
    destination: str = Field(..., json_schema_extra={"example": "Guadalajara, México"})
    waypoints: list[str] | None = Field(None, json_schema_extra={"example": ["Puebla, México"]})
    avoid: list[str] | None = Field(
        None,
        description="Elementos a evitar: tolls, highways, ferries",
        json_schema_extra={"example": ["tolls"]}
    )
 
 
class MatrixRequest(BaseModel):
    origins: list[str] = Field(..., json_schema_extra={"example": ["CDMX", "Monterrey"]})
    destinations: list[str] = Field(..., json_schema_extra={"example": ["Guadalajara", "Puebla"]})
    with_traffic: bool = Field(False, description="Incluir tráfico en tiempo real")
