# Portugalete — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.portugalete.org |
| Sede PortugaleteON | https://www.portugaleteon.com |
| Urbanismo (servicio) | https://www.portugalete.org/es-ES/Servicios/Urbanismo/Paginas/default.aspx |
| Urbanismo y Obras | https://www.portugalete.org/es-ES/VivirenPortugalete/UrbanismoyObras/Paginas/default.aspx |
| Trámites urbanismo | https://www.portugalete.org/es-ES/Ayuntamiento/TramitesCiudadanos/Paginas/Urbanismo.aspx |
| Tablón de anuncios | https://www.portugalete.org/es-ES/Tramites/tablonanuncios/ayuntamiento/Paginas/default.aspx |
| Consejo Asesor Planeamiento | https://www.portugalete.org/es-ES/Ayuntamiento/Corporacionmunicipal/Paginas/ConsejoAsesordePlaneamientoMunicipal.aspx |
| Transparencia (Zabaltzen) | https://zabaltzen.portugalete.org/es/transparencia/ |
| Open Data Bizkaia — planeamiento | https://www.opendatabizkaia.eus/es/catalogo/planeamiento-urbanistico-portugalete |
| Dump JSON datos globales 2023-2026 | https://www.opendatabizkaia.eus/es/datastore/dump/1bf67aeb-8a08-4df4-9f8c-3392c88dbcda/datos-globales-planeamiento-portugalete-2023-2026?format=json |

## Cómo se listan expedientes / proyectos

1. **Tablón SharePoint** — Listado HTML «Anuncios en vigor» con título, remitente, categoría, vigencia y enlace PDF. No hay API JSON; el adapter parsea bloques de texto (`Remitente` / `Categoría` / `Tiempo de vigencia`).
2. **Open Data Bizkaia** — Dataset agregado trimestral (datos globales y calificación pormenorizada); orientativo, sin código de expediente municipal enlazado.
3. **Semillas portal** — Páginas de urbanismo y PGOU (documentación en PDF enlazados desde HTML cuando el portal responde).

No hay visor municipal de consulta de expediente por código (patrón distinto de Madrid SIGMA).

## Licencias de obra

- Trámites descritos en `TramitesCiudadanos/Paginas/Urbanismo_*.aspx` (actividad clasificada, obras menores en dominio público, etc.).
- **No** hay dataset público de licencias concedidas con dirección/coordenadas.
- El tablón puede publicar anuncios de licencias/obras; el adapter los detecta por regex.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Diputación Foral de Bizkaia — ArcGIS `Plangintza_Planeamiento/MapServer` capas 1–3 (clasificación: urbano / urbanizable / no urbanizable), filtro `Municipio='PORTUGALETE'`, `returnGeometry=true`, `outSR=4326`, `f=geojson`.
  - Open Data Bizkaia — estadístico sin geometría por expediente.
- **Estrategia:** filas representativas de clasificación PGOU municipal con polígono ArcGIS; anuncios del tablón sin enlace GIS → sin `geom_geojson` (geocode con centroide municipal).
- **Limitaciones:**
  - `www.portugalete.org` suele **timeout** desde entornos cloud (504); tablón y semillas pueden quedar vacíos fuera de red local.
  - `www.opendatabizkaia.eus` también puede timeout intermitente.
  - Sin campo expediente en capas de clasificación (no join tablón ↔ polígono).

## Limitaciones técnicas

- CMS SharePoint (portugalete.org) + PortugaleteON (CMS 4.x).
- Sin boletín asociado en cola (`bocm_count: 0`).
- PGOU documental en tomos (memoria, normativa, catálogo protegidos) en portal; no scrapeados exhaustivamente.
