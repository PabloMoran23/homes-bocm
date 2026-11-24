# Sestao — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.sestao.eus |
| Urbanismo (servicio) | https://www.sestao.eus/es-ES/Ayuntamiento/servicios/Urbanismo/Paginas/default.aspx |
| Ibarzaharra (PEOU / PAU / documentación) | https://www.sestao.eus/es-ES/Ayuntamiento/servicios/Urbanismo/Paginas/ibarzaharra.aspx |
| Tablón de anuncios | https://www.sestao.eus/es-ES/Tramites/tablonanuncios/ayuntamiento/Paginas/default.aspx |
| Trámites | https://www.sestao.eus/es-ES/Tramites/Paginas/default.aspx |
| Registro PUR Bizkaia (municipio **84** SESTAO) | https://www.bizkaia.eus/es/planeamiento-urbanistico-buscador |
| Open Data Bizkaia — planeamiento | https://www.opendatabizkaia.eus/es/catalogo/planeamiento-urbanistico-sestao |
| Dump JSON datos globales 2023-2026 | https://www.opendatabizkaia.eus/es/datastore/dump/62fbe853-fe96-443a-a826-a7e39f2ee938/datos-globales-planeamiento-sestao-2023-2026?format=json |
| Inventario / registro vasco (contexto) | https://www.euskadi.eus/legislacion-urbanistica/web01-sede/es/ |

## Cómo se listan expedientes / proyectos

1. **Registro PUR Diputación Foral de Bizkaia** — Formulario Liferay con filtro por municipio (`select-municipios=84`). Devuelve tarjetas HTML con año, título del instrumento, código entre paréntesis y enlace a ficha (`idInstrumento`). ~25 instrumentos visibles (PEOU Naval, Ibarzaharra, modificaciones PGOU, etc.).
2. **Portal SharePoint sestao.eus** — Páginas de urbanismo con listas de PDFs (p. ej. Ibarzaharra AIS_IB_06). Tablón de anuncios con anuncios en vigor (estructura similar a Portugalete/Santurtzi: título + remitente + categoría + vigencia, o bloques h3+PDF).
3. **Open Data Bizkaia** — Datos globales y calificación pormenorizada (orientativo, sin código de expediente enlazado a GIS municipal).

No hay visor municipal tipo SIGMA Madrid con consulta por código de expediente.

## Licencias de obra

- Trámites descritos en el portal municipal; **no** hay dataset público de licencias concedidas con coordenadas.
- El tablón puede publicar anuncios de licencias/obras; el adapter los detecta por regex cuando el portal responde.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Diputación Foral de Bizkaia — ArcGIS `Plangintza_Planeamiento/MapServer` capas 1–3 (clasificación: urbano / urbanizable / no urbanizable), filtro `Municipio='SESTAO'`, `returnGeometry=true`, `outSR=4326`, `f=geojson`.
  - Open Data Bizkaia — estadístico sin geometría por expediente.
  - Registro PUR — metadatos de instrumentos sin polígono descargable por expediente.
- **Estrategia:** filas representativas de clasificación PGOU municipal con polígono ArcGIS; instrumentos PUR y anuncios del tablón sin join GIS → sin `geom_geojson` (geocode con centroide municipal o de polígono ArcGIS).
- **Limitaciones:**
  - `www.sestao.eus` y `www.opendatabizkaia.eus` pueden **timeout en handshake SSL** desde entornos cloud; tablón, semillas y opendata pueden quedar vacíos fuera de red local.
  - `geo.bizkaia.eus` y `www.bizkaia.eus` suelen ser accesibles desde CI/cloud.
  - Sin campo expediente en capas de clasificación (no join tablón ↔ polígono).

## Limitaciones técnicas

- CMS SharePoint (sestao.eus), mismo patrón que municipios costeros de Bizkaia.
- Sin boletín asociado en cola (`bocm_count: 0`).
- Documentación PGOU/PEOU principalmente en PDF en portal e Ibarzaharra.
