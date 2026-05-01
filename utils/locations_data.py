#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BASE DE DATOS DE PAÍSES Y CIUDADES
Latinoamérica, Europa, Norteamérica
"""

PAISES_CIUDADES = {
    # LATINOAMÉRICA
    "Colombia": [
        "Bogotá", "Medellín", "Cali", "Barranquilla", "Cartagena",
        "Bucaramanga", "Pereira", "Manizales", "Ibagué", "Cúcuta",
        "Pasto", "Santa Marta", "Villavicencio", "Armenia", "Popayán"
    ],
    "México": [
        "Ciudad de México", "Guadalajara", "Monterrey", "Puebla", "Tijuana",
        "León", "Querétaro", "Mérida", "Cancún", "Aguascalientes",
        "San Luis Potosí", "Hermosillo", "Saltillo", "Mexicali", "Chihuahua"
    ],
    "Argentina": [
        "Buenos Aires", "Córdoba", "Rosario", "Mendoza", "La Plata",
        "San Miguel de Tucumán", "Mar del Plata", "Salta", "Santa Fe",
        "San Juan", "Resistencia", "Neuquén", "Bahía Blanca"
    ],
    "Chile": [
        "Santiago", "Valparaíso", "Concepción", "La Serena", "Antofagasta",
        "Temuco", "Rancagua", "Talca", "Arica", "Chillán",
        "Iquique", "Puerto Montt", "Coquimbo", "Osorno"
    ],
    "Perú": [
        "Lima", "Arequipa", "Cusco", "Trujillo", "Chiclayo",
        "Piura", "Iquitos", "Huancayo", "Tacna", "Pucallpa",
        "Cajamarca", "Ayacucho", "Juliaca", "Puno"
    ],
    "Brasil": [
        "São Paulo", "Rio de Janeiro", "Brasília", "Salvador", "Fortaleza",
        "Belo Horizonte", "Manaus", "Curitiba", "Recife", "Porto Alegre",
        "Belém", "Goiânia", "Guarulhos", "Campinas", "São Luís"
    ],
    "Ecuador": [
        "Quito", "Guayaquil", "Cuenca", "Santo Domingo", "Machala",
        "Durán", "Portoviejo", "Manta", "Loja", "Ambato"
    ],
    "Bolivia": [
        "La Paz", "Santa Cruz", "Cochabamba", "Sucre", "Oruro",
        "Tarija", "Potosí", "El Alto", "Trinidad"
    ],
    "Paraguay": [
        "Asunción", "Ciudad del Este", "San Lorenzo", "Luque",
        "Capiatá", "Encarnación", "Pedro Juan Caballero"
    ],
    "Uruguay": [
        "Montevideo", "Salto", "Paysandú", "Las Piedras", "Rivera",
        "Maldonado", "Tacuarembó", "Melo", "Mercedes"
    ],
    "Venezuela": [
        "Caracas", "Maracaibo", "Valencia", "Barquisimeto", "Maracay",
        "Ciudad Guayana", "Barcelona", "Maturín", "Puerto La Cruz"
    ],
    "Costa Rica": [
        "San José", "Alajuela", "Cartago", "Heredia", "Limón",
        "Puntarenas", "Liberia", "Paraíso", "Desamparados"
    ],
    "Panamá": [
        "Ciudad de Panamá", "San Miguelito", "Tocumen", "David",
        "Arraiján", "Colón", "Las Cumbres", "La Chorrera"
    ],
    
    # NORTEAMÉRICA
    "Estados Unidos": [
        "New York", "Los Angeles", "Chicago", "Houston", "Phoenix",
        "Philadelphia", "San Antonio", "San Diego", "Dallas", "San Jose",
        "Austin", "Jacksonville", "Fort Worth", "Columbus", "Charlotte",
        "San Francisco", "Indianapolis", "Seattle", "Denver", "Boston",
        "Nashville", "Detroit", "Portland", "Las Vegas", "Miami",
        "Atlanta", "Washington DC", "Baltimore", "Milwaukee", "Orlando"
    ],
    "Canadá": [
        "Toronto", "Montreal", "Vancouver", "Calgary", "Edmonton",
        "Ottawa", "Winnipeg", "Quebec City", "Hamilton", "Kitchener",
        "London", "Victoria", "Halifax", "Saskatoon", "Regina"
    ],
    
    # EUROPA
    "España": [
        "Madrid", "Barcelona", "Valencia", "Sevilla", "Zaragoza",
        "Málaga", "Murcia", "Palma", "Las Palmas", "Bilbao",
        "Alicante", "Córdoba", "Valladolid", "Vigo", "Gijón",
        "Granada", "Vitoria", "San Sebastián", "Oviedo", "Santander"
    ],
    "Reino Unido": [
        "London", "Manchester", "Birmingham", "Leeds", "Glasgow",
        "Liverpool", "Newcastle", "Sheffield", "Bristol", "Belfast",
        "Edinburgh", "Leicester", "Brighton", "Cardiff", "Nottingham"
    ],
    "Francia": [
        "Paris", "Marseille", "Lyon", "Toulouse", "Nice",
        "Nantes", "Strasbourg", "Montpellier", "Bordeaux", "Lille",
        "Rennes", "Reims", "Le Havre", "Toulon", "Grenoble"
    ],
    "Alemania": [
        "Berlin", "Hamburg", "Munich", "Cologne", "Frankfurt",
        "Stuttgart", "Dusseldorf", "Dortmund", "Essen", "Leipzig",
        "Bremen", "Dresden", "Hanover", "Nuremberg", "Duisburg"
    ],
    "Italia": [
        "Rome", "Milan", "Naples", "Turin", "Palermo",
        "Genoa", "Bologna", "Florence", "Bari", "Catania",
        "Venice", "Verona", "Messina", "Padua", "Trieste"
    ],
    "Portugal": [
        "Lisbon", "Porto", "Vila Nova de Gaia", "Amadora", "Braga",
        "Funchal", "Coimbra", "Setúbal", "Almada", "Aveiro"
    ],
    "Países Bajos": [
        "Amsterdam", "Rotterdam", "The Hague", "Utrecht", "Eindhoven",
        "Tilburg", "Groningen", "Almere", "Breda", "Nijmegen"
    ],
    "Bélgica": [
        "Brussels", "Antwerp", "Ghent", "Charleroi", "Liège",
        "Bruges", "Namur", "Leuven", "Mons", "Mechelen"
    ],
    "Suiza": [
        "Zurich", "Geneva", "Basel", "Lausanne", "Bern",
        "Winterthur", "Lucerne", "St. Gallen", "Lugano", "Biel/Bienne"
    ],
    "Suecia": [
        "Stockholm", "Gothenburg", "Malmö", "Uppsala", "Västerås",
        "Örebro", "Linköping", "Helsingborg", "Jönköping", "Norrköping"
    ],
    "Noruega": [
        "Oslo", "Bergen", "Stavanger", "Trondheim", "Drammen",
        "Fredrikstad", "Kristiansand", "Sandnes", "Tromsø", "Sarpsborg"
    ],
    "Dinamarca": [
        "Copenhagen", "Aarhus", "Odense", "Aalborg", "Esbjerg",
        "Randers", "Kolding", "Horsens", "Vejle", "Roskilde"
    ],
    "Irlanda": [
        "Dublin", "Cork", "Limerick", "Galway", "Waterford",
        "Drogheda", "Dundalk", "Swords", "Bray", "Navan"
    ],
    "Polonia": [
        "Warsaw", "Krakow", "Lodz", "Wroclaw", "Poznan",
        "Gdansk", "Szczecin", "Bydgoszcz", "Lublin", "Katowice"
    ],
    "Austria": [
        "Vienna", "Graz", "Linz", "Salzburg", "Innsbruck",
        "Klagenfurt", "Villach", "Wels", "Sankt Pölten", "Dornbirn"
    ]
}


# Modalidades de trabajo
MODALIDADES = {
    "presencial": "Presencial",
    "hibrido": "Híbrido",
    "remoto": "Remoto"
}


def get_paises_por_region():
    """Obtener países agrupados por región"""
    latinoamerica = [
        "Colombia", "México", "Argentina", "Chile", "Perú", "Brasil",
        "Ecuador", "Bolivia", "Paraguay", "Uruguay", "Venezuela",
        "Costa Rica", "Panamá"
    ]
    
    norteamerica = ["Estados Unidos", "Canadá"]
    
    europa = [
        "España", "Reino Unido", "Francia", "Alemania", "Italia",
        "Portugal", "Países Bajos", "Bélgica", "Suiza", "Suecia",
        "Noruega", "Dinamarca", "Irlanda", "Polonia", "Austria"
    ]
    
    return {
        "Latinoamérica": latinoamerica,
        "Norteamérica": norteamerica,
        "Europa": europa
    }


def get_ciudades_por_pais(pais):
    """Obtener ciudades de un país"""
    return PAISES_CIUDADES.get(pais, [])


def get_all_paises():
    """Obtener todos los países"""
    return sorted(PAISES_CIUDADES.keys())


if __name__ == "__main__":
    print(f"Total de países: {len(PAISES_CIUDADES)}")
    print(f"\nPaíses por región:")
    for region, paises in get_paises_por_region().items():
        print(f"  {region}: {len(paises)} países")
