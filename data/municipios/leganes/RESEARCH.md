# Leganés — investigación portal ayuntamiento

## Portal base

- **URL:** https://www.leganes.org
- **CMS:** Liferay (`leganes-theme`)
- **Sede electrónica:** https://sede.leganes.org (STA / CarpetaPublic — ver limitaciones)

## Fuentes de planeamiento / expedientes

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Urbanismo e Industria | `/urbanismo-e-industria` | Liferay menú + enlaces | Hub de planeamiento |
| Planes Parciales | `/planes-parciales-urbanismo` | Liferay `/documents/…/nombre.pdf/uuid` | Textos, planos y BOCM de PP (PP-1 Oeste, etc.) |
| Planes Especiales | `/planes-especiales` | Liferay documentos | Anuncios IP, edictos, notificaciones (ej. `Anuncio 2024-2W-URB-PLNESP.pdf`) |
| Planeamiento en tramitación | `/planeamiento-en-tramitacion` | HTML + PDF | Instrumentos en curso |
| PGOU | `/acuerdo-de-aprobacion-plan-general`, `/memoria-del-plan-general`, `/normas-del-plan-general`, `/planos-del-plan-general` | PDFs | Plan General vigente |
| Modificaciones / correcciones PGOU | `/modificaciones-puntuales-del-pgou`, `/correccion-de-errores-del-pgou` | PDFs | Modificaciones puntuales |
| Plan PERI Casco Antiguo | `/texto-del-plan-peri-casco-antiguo`, `/planos-del-plan-peri-casco-antiguo` | PDFs | PERI |
| Sectorización A-42 | `/plan-de-sectorizacion-autovia-de-toledo-norte` | PDFs | Plan sectorización |
| Catálogo edificios | `/plano-del-catalogo-de-edificios-protegidos` | PDFs | Patrimonio urbanístico |
| Sede tablón STA | `sede.leganes.org/.../PAGE_CODE=PTS2_TABLON` | JSON embebido `dataset_PTS2_TABLON` | Tablón de anuncios (licencias, IP) — **inaccesible** desde scraper |

Estructura Liferay documentos:

```html
<a href="/documents/113177/271814/NOMBRE.pdf/uuid?t=...">...</a>
```

El título del expediente se extrae del segmento `NOMBRE.pdf` en la URL (URL-decoded).

## Fuentes de licencias

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Trámites urbanismo | `https://sede.leganes.org/` (enlace desde web) | Sede STA | Catálogo de trámites (licencias, comunicaciones) — **inaccesible** |
| Sede catálogo | `sede.leganes.org/.../PAGE_CODE=CATALOGO` | STA | Trámites licencia/obra — **inaccesible** |
| Planes especiales / tablón | PDFs con «licencia», «anuncio» | PDF | Sin listado estructurado de concesiones |
| Obras | `/obras-e-infraestructuras`, `/normativa-obras` | HTML + PDFs | Normativa de obras, no concesiones |

No hay dataset público de licencias concedidas con fecha/distrito/coordenadas en la web municipal accesible. Paridad licencias: páginas informativas de trámites (sede) + búsqueda en documentos publicados.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - **IDEM WFS** (Comunidad de Madrid): `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO ILIKE '%LEGAN%'`
  - Campos útiles: `DS_NOMB_AMB` (UE-11, etc.), `DS_FIG_DES`, `CD_REUR`, geometría `Polygon`
  - No hay visor ArcGIS municipal ni enlace expediente→polígono en el portal
- **Estrategia:** Tras extraer metadatos del proyecto, consultar WFS por coincidencia de nombre de ámbito/plan en el título (`PP-1`, `UE-11`, `PLNESP`, etc.) y rellenar `geom_geojson` cuando hay match
- **Limitaciones:**
  - Geometría solo para ámbitos de planeamiento refundido (SIT regional), no para licencias ni anuncios puntuales
  - Sede/tablon inaccesible (TLS reset desde entorno cloud)
  - PDFs de planos sin georreferencia embebida
  - Sin API municipal de expedientes

## Limitaciones generales

1. **Sede electrónica** (`sede.leganes.org`): connection reset desde el entorno de scraping; se intenta con `sede_insecure_ssl` y se degrada a web Liferay.
2. Sin datos abiertos ni API de expedientes urbanísticos.
3. **Licencias:** no hay tablón scrapeable; solo trámites informativos.
4. **Fechas:** inferidas de nombre PDF, timestamp `?t=` en URL Liferay o año en título.
5. Miles de planos técnicos en planes parciales; el adapter filtra por relevancia (anuncios, textos, memorias, BOCM) y registros con palabras clave urbanísticas.

## Estrategia adapter

- Crawl determinista de páginas semilla urbanismo en `www.leganes.org`.
- Extracción PDF Liferay (`/documents/groupId/folderId/NOMBRE.pdf/uuid`).
- Intento sede STA tablón (fallo silencioso si bloqueado).
- Licencias: enlace trámites sede + PDFs con keywords licencia.
- Geometría: enriquecimiento opcional vía WFS IDEM `VPLA_V_AMBITO`.
