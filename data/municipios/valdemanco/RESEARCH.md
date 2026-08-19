# Investigación portal — Valdemanco

Municipio: **Valdemanco** (`valdemanco`) — Comunidad de Madrid, provincia Valdemanco, Madrid.  
BOCM (`bocm`): 4 entradas históricas.

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.valdemanco.org | WordPress (Cryout Creations) |
| Servicios municipales | https://www.valdemanco.org/servicios-municipales/ | Urbanismo: licencias de obra y consultas |
| Impresos | https://www.valdemanco.org/impresos/ | PDFs licencia obra mayor/menor, primera ocupación |
| Sede electrónica | https://valdemanco.sedelectronica.es | espublico gestiona (Wicket) |
| Tablón anuncios | https://valdemanco.sedelectronica.es/board | Tabla HTML; actualmente sin filas urbanísticas |
| Ordenanzas (transparencia) | https://valdemanco.sedelectronica.es/transparency/04c03607-6da4-46cd-8d65-b743eb02a665/ | PDFs ordenanzas municipales |
| Portal transparencia | https://valdemanco.sedelectronica.es/transparency/ | Empleo, presupuestos, cuenta general |
| Instancias | https://valdemanco.sedelectronica.es/info.0 | Presentación electrónica (Cl@ve) |

## Cómo se listan expedientes / proyectos

1. **No hay visor de expedientes** ni listado público de información pública por código de expediente.
2. **SITCM WFS** — 21 polígonos de ámbitos de planeamiento (`SAU-*`, `UE-*`) vía GeoServer Comunidad de Madrid.
3. **Transparencia ordenanzas** — documentos PDF en sede (preview-document UUID).
4. **Tablón sede** — una fila de empleo en el momento de la investigación; sin planeamiento.
5. **WordPress** — noticias municipales sin sección dedicada de urbanismo; impresos con formularios.

## Cómo se publican licencias

- **No hay registro público** de licencias concedidas (fecha, tipo, ubicación).
- Formularios PDF en `/impresos/`: obra mayor, obra menor, primera ocupación, declaración responsable actividades.
- Trámites presenciales / sede con Cl@ve; urbanismo gestiona licencias en oficina municipal.
- Tablón podría publicar licencias pero no hay filas urbanísticas actualmente.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor SITCM: https://idem.madrid.org/cartografia/sitcm/html/visor.htm (municipio Valdemanco)
  - WFS GeoServer IDEM: `sitcm:VPLA_V_AMBITO` con `DS_MUNICIPIO='VALDEMANCO'` (21 features, EPSG:4326)
  - Campos: `DS_NOMB_AMB` (ej. `UE-S.8`, `SAU-1 (APLAZADO)`), `DS_CLAS_SUE`, `DS_FIG_DES`
- **Estrategia:** ingestar ámbitos SITCM como proyectos de planeamiento con `geom_geojson`; enriquecer filas si el título menciona código UE/SAU.
- **Limitaciones:** sin geometría por expediente individual ni licencia; tablón sin coords; sin visor municipal propio.

## Limitaciones generales

- Catálogo `/dossier` de sede muy lento o sin respuesta en scraping automatizado.
- Sin datos abiertos GeoJSON municipal.
- Licencias solo como formularios informativos (patrón Pozuelo).
- scrape determinista sobre HTML/WFS; sin LLM.

## Referencia adapter

Patrón: `patones.py` / `venturada.py` (WordPress impresos + espublico sede + SITCM WFS).
