from pydantic import BaseModel, Field
from typing import List, Optional

class Airport(BaseModel):
    id: str
    iata: str
    icao: str
    name: str
    city: str
    country: str
    countryCode: str
    region: Optional[str] = None
    regionCode: Optional[str] = None
    type: str
    latitude: float
    longitude: float
    commercialPriority: int = Field(default=0)
    aliases: List[str] = Field(default_factory=list)
    normalizedIata: Optional[str] = None
    normalizedCity: Optional[str] = None
    normalizedName: Optional[str] = None
    normalizedAliases: List[str] = Field(default_factory=list)
    normalizedTokens: List[str] = Field(default_factory=list)

class CityGroup(BaseModel):
    id: str
    code: Optional[str] = None
    displayName: str
    city: str
    region: Optional[str] = None
    country: str
    countryCode: str
    airportIatas: List[str] = Field(default_factory=list)
    aliases: List[str] = Field(default_factory=list)
    priority: int = Field(default=0)
    searchText: Optional[str] = None
    normalizedCode: Optional[str] = None
    normalizedDisplayName: Optional[str] = None
    normalizedAliases: List[str] = Field(default_factory=list)
    normalizedTokens: List[str] = Field(default_factory=list)

class RegionGroup(BaseModel):
    id: str
    displayName: str
    region: str
    regionCode: str
    country: str
    countryCode: str
    airportIatas: List[str] = Field(default_factory=list)
    aliases: List[str] = Field(default_factory=list)
    priority: int = Field(default=0)
    searchText: Optional[str] = None
    normalizedDisplayName: Optional[str] = None
    normalizedAliases: List[str] = Field(default_factory=list)
    normalizedTokens: List[str] = Field(default_factory=list)

class Country(BaseModel):
    code: str
    name: str
