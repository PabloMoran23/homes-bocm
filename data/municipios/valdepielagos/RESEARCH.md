# Investigación portal — Valdepiélagos

Municipio: **Valdepiélagos** (`valdepielagos`) — Comunidad de Madrid, provincia Madrid.  
BOCM (`bocm`): 5 entradas históricas.

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.valdepielagos.es | WordPress + tema Enfold |
| Planeamiento | https://www.valdepielagos.es/planeamiento/ | NNSS 2000 + subsanaciones SAU 2/4/5 (PDFs en listas icono) |
| Servicios técnicos | https://www.valdepielagos.es/tecnico-municipal/ | Impresos urbanísticos (toggles: licencia, DR, acto comunicado) |
| Sede electrónica | https://valdepielagos.sedelectronica.es | espublico gestiona |
| Tablón anuncios | https://valdepielagos.sedelectronica.es/board/ | Tabla HTML (~4 filas; sin urbanismo activo) |
| Transparencia | https://valdepielagos.sedelectronica.es/transparency/ | Categoría «Urbanismo, obras y medio ambiente» (12 docs; carga SPA) |

## Cómo se listan expedientes / proyectos

1. **Página Planeamiento (Enfold)** — secciones `h4` con listas `avia-icon-list`: NNSS (acuerdo, catálogo, memoria, normas, planos P1–P5) y subsanaciones SAU 5 (2000) y SAU 2/4 (2007).
2. **WFS SITCM** — 5 ámbitos `AR-1 SAU1` … `SAU5` (estado APLAZADO) con polígonos en GeoServer CM.
3. **Tablón sede** — anuncios generales (calendario fiscal, fiestas, seguridad); sin expedientes de planeamiento en curso.
4. **Transparencia sede** — categoría urbanismo con documentos históricos (no scrapeable sin JS en esta investigación).

No hay visor municipal propio ni listado de expedientes por código.

## Cómo se publican licencias

- **No hay registro público** de licencias concedidas (fecha, tipo, ubicación).
- Impresos descargables en `/tecnico-municipal/`: ocupación vía pública, acto comunicado, declaración responsable urbanística, solicitud licencia urbanística, declaración responsable actividad.
- Trámites presenciales (jueves 15:30–17:00) y email `stecnicos.valdepielagos@gmail.com`.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor SITCM: https://www.madrid.org/cartografia/sitcm/html/visor.htm (municipio Valdepiélagos)
  - WFS GeoServer IDEM: `sitcm:VPLA_V_AMBITO` con `DS_MUNICIPIO='VALDEPIÉLAGOS'` (5 features)
  - Campos: `DS_NOMB_AMB` (ej. `AR-1 SAU5 (APLAZADO)`), `DS_CLAS_SUE`, `DS_FIG_DES`
- **Estrategia:** ingestar ámbitos SITCM como proyectos con `geom_geojson`; enriquecer filas de planeamiento si el título menciona SAU o código de ámbito.
- **Limitaciones:** sin geometría por expediente individual; licencias sin georreferencia; tablón sin entradas urbanísticas; transparencia requiere JS.

## Limitaciones generales

- Portal sin API de expedientes; scrape determinista sobre HTML estático + WFS.
- Documentación de planeamiento mayoritariamente histórica (NNSS 2000).
- Tablón sede con pocas filas y sin paginación visible.

## Referencia adapter

Patrón: `torremocha_de_jarama.py` / `venturada.py` (WordPress + espublico sede + SITCM WFS).
