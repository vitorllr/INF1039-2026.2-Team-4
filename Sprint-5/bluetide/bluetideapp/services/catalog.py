from dataclasses import dataclass


# A fixed local frame keeps the simplified coast diagram stable between loads.
# Coordinates are WGS84 decimal degrees, projected to local meters. This diagram
# is illustrative, not suitable for navigation.
MAP_BOUNDS = {
    "south": -23.002,
    "north": -22.975,
    "west": -43.226,
    "east": -43.188,
}
MAP_METERS_PER_DEGREE_LATITUDE = 111_320
MAP_METERS_PER_DEGREE_LONGITUDE = 102_478  # cos(22.99 degrees) * 111,320


@dataclass(frozen=True)
class BeachPoint:
    slug: str
    name: str
    posto: str
    neighborhood: str
    latitude: float
    longitude: float
    summary: str

    @property
    def display_name(self) -> str:
        return f"{self.name} · {self.posto}"

    @property
    def map_x(self) -> int:
        return round((self.longitude - MAP_BOUNDS["west"]) * MAP_METERS_PER_DEGREE_LONGITUDE)

    @property
    def map_y(self) -> int:
        return round((MAP_BOUNDS["north"] - self.latitude) * MAP_METERS_PER_DEGREE_LATITUDE)


BEACH_POINTS = (
    BeachPoint(
        slug="ipanema-posto-7",
        name="Ipanema",
        posto="Posto 7",
        neighborhood="Arpoador",
        latitude=-22.9884,
        longitude=-43.1934,
        summary="Perto do Arpoador, com mar mais exposto.",
    ),
    BeachPoint(
        slug="ipanema-posto-8",
        name="Ipanema",
        posto="Posto 8",
        neighborhood="Ipanema",
        latitude=-22.9869,
        longitude=-43.2005,
        summary="Trecho central com acesso pela Farme de Amoedo.",
    ),
    BeachPoint(
        slug="ipanema-posto-9",
        name="Ipanema",
        posto="Posto 9",
        neighborhood="Ipanema",
        latitude=-22.9868,
        longitude=-43.2050,
        summary="Trecho movimentado próximo à Rua Vinícius de Moraes.",
    ),
    BeachPoint(
        slug="ipanema-posto-10",
        name="Ipanema",
        posto="Posto 10",
        neighborhood="Ipanema",
        latitude=-22.9861,
        longitude=-43.2115,
        summary="Trecho mais próximo ao Jardim de Alah.",
    ),
    BeachPoint(
        slug="ipanema-posto-11",
        name="Ipanema",
        posto="Posto 11",
        neighborhood="Leblon",
        latitude=-22.9870,
        longitude=-43.2204,
        summary="Limite com o Leblon e acesso pelo canal do Jardim de Alah.",
    ),
)

BEACH_POINTS_BY_SLUG = {point.slug: point for point in BEACH_POINTS}
