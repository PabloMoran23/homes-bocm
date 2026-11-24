# Villarrobledo — investigación portal ayuntamiento

Municipio: **Villarrobledo** (`villarrobledo`), provincia Albacete, Castilla-La Mancha. INE **02081** (código entidad Diputación Albacete / Sedipualba `P0208100H`).

## URLs base y semillas

| Recurso | URL | Notas |
|---------|-----|-------|
| Web oficial | https://www.villarrobledo.com | CMS propio PHP; SSL válido |
| Área Urbanismo y Obras | https://www.villarrobledo.com/area.php?id=17 | Texto PGOU + ~20 PDFs normativa/planos |
| Tablón (web) | https://www.villarrobledo.com/ayuntamiento/anuncios.php | Enlace al tablón Sedipualba |
| Plano y callejero | https://www.villarrobledo.com/plano.php | Leaflet + IGN PNOA; búsqueda Geoapify (sin capa urbanística) |
| Sede electrónica | https://villarrobledo.sedipualba.es | ASP.NET Sedipualba |
| Tablón anuncios | https://villarrobledo.sedipualba.es/tablondeanuncios/default.aspx | HTML + filtros área/mes |
| Tablón RSS | https://villarrobledo.sedipualba.es/tablondeanuncios/tablon_rss.aspx | ISO-8859-1 |
| Catálogo trámites URB | https://villarrobledo.sedipualba.es/catalogoservicios.aspx?area=302 | Área «Urbanismo y Actividades» (listado vacío en HTML estático) |
| Trámites web (licencias) | https://www.villarrobledo.com/tramite.php?id=83 (etc.) | Enlace «Por Internet» → `carpetaciudadana/tramite.aspx?idtramite=…` |
| Transparencia | https://transparencia.villarrobledo.com | Catálogo trámites; duplica info sede |

## Cómo se listan expedientes / proyectos

- **Web — área Urbanismo:** páginas estáticas con documentación del PGOU (PDFs en `/admin/data/docs/*.pdf` con títulos en `<span>`).
- **Tablón Sedipualba:** RSS + HTML; edictos varios (información pública aguas, ocupación vía pecuaria, etc.). PDFs en `documento.aspx?id=…`.
- **Sede:** trámites informativos (licencia de obras, DR obra menor, parcelación…) sin listado público de expedientes abiertos.

Patrón de scrape: PDFs PGOU + fila POM desde ArcGIS CLM + tablón RSS (regex urbanismo) + semillas área urbanismo.

## Licencias de obra

- No hay registro público de licencias concedidas con coordenadas.
- Trámites informativos en web + instancias Sedipualba (`carpetaciudadana/tramite.aspx`).
- Adapter devuelve trámites URB detectados + fila referencia al tablón.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ArcGIS CLM `Vector/Planeamiento_Municipal/MapServer/0` — `COD_INE='02081'` → polígono **Plan General de Ordenación Urbana** (GeoJSON WGS84).
  - `plano.php`: callejero Leaflet + ortofoto IGN; sin enlace a parcelas/expedientes.
  - PDFs/tablon sin georreferencia explícita.
- **Estrategia:** proyecto `PGOU — Villarrobledo (CLM)` con `geom_geojson` del servicio regional; documentación PDF y edictos sin geometría (centroide municipio en orquestador).
- **Limitaciones:** sin visor urbanístico municipal ni WFS parcelario; CLM no distingue expedientes individuales.

## Limitaciones generales

- Catálogo Sedipualba área 302 no expone enlaces `tramite.aspx` en HTML inicial (solo navegación); trámites licencia se resuelven desde fichas `tramite.php` del área Urbanismo.
- Tablón mezcla anuncios no urbanísticos (personal, cultura); filtrado por regex.
- Presentación de instancias requiere certificado/Cl@ve/email Sedipualba.
