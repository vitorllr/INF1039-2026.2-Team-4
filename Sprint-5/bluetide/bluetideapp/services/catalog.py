from dataclasses import dataclass


@dataclass(frozen=True)
class BeachPoint:
    slug: str
    name: str
    posto: str
    neighborhood: str
    latitude: float
    longitude: float
    map_x: int
    map_y: int
    summary: str

    @property
    def display_name(self) -> str:
        return f"{self.name} · {self.posto}"


BEACH_POINTS = (
    BeachPoint(
        slug="ipanema-posto-7",
        name="Ipanema",
        posto="Posto 7",
        neighborhood="Arpoador",
        latitude=-22.9884,
        longitude=-43.1934,
        map_x=83,
        map_y=67,
        summary="Perto do Arpoador, com mar mais exposto.",
    ),
    BeachPoint(
        slug="ipanema-posto-8",
        name="Ipanema",
        posto="Posto 8",
        neighborhood="Ipanema",
        latitude=-22.9869,
        longitude=-43.2005,
        map_x=66,
        map_y=58,
        summary="Trecho central com acesso pela Farme de Amoedo.",
    ),
    BeachPoint(
        slug="ipanema-posto-9",
        name="Ipanema",
        posto="Posto 9",
        neighborhood="Ipanema",
        latitude=-22.9868,
        longitude=-43.2050,
        map_x=50,
        map_y=52,
        summary="Trecho movimentado próximo à Rua Vinícius de Moraes.",
    ),
    BeachPoint(
        slug="ipanema-posto-10",
        name="Ipanema",
        posto="Posto 10",
        neighborhood="Ipanema",
        latitude=-22.9861,
        longitude=-43.2115,
        map_x=34,
        map_y=45,
        summary="Trecho mais próximo ao Jardim de Alah.",
    ),
    BeachPoint(
        slug="ipanema-posto-11",
        name="Ipanema",
        posto="Posto 11",
        neighborhood="Leblon",
        latitude=-22.9870,
        longitude=-43.2204,
        map_x=18,
        map_y=38,
        summary="Limite com o Leblon e acesso pelo canal do Jardim de Alah.",
    ),
)

BEACH_POINTS_BY_SLUG = {point.slug: point for point in BEACH_POINTS}
