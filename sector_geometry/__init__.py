"""
Corre en segundo plano: encola pares (municipio, sector) desde CSVs parseados,
intenta resolver geometría vía resolvers configurables (ArcGIS REST, …) y
persiste GeoJSON + metadatos en SQLite.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
