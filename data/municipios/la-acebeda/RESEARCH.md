# La Acebeda — investigación portal ayuntamiento

## URLs base y páginas semilla

| Recurso | URL | Estado |
|---------|-----|--------|
| Web corporativa | https://laacebeda.org | OK (WordPress + The7 + Yoast) |
| Urbanismo | https://laacebeda.org/urbanismo/ | OK — cronogramas + ordenanza construcción |
| Cronograma Casa de la Maestra | https://laacebeda.org/casa-de-la-maestra/ | OK — PDF plano consultorio |
| Cronograma Manga Ganadera | https://laacebeda.org/manga-ganadera/ | OK — PDF plano |
| Cronograma Acondicionamiento Camino | https://laacebeda.org/acondicionamiento-camino/ | OK — PDF planos embellecimiento |
| Ordenanzas municipales | https://laacebeda.org/ordenanzas-municipales/ | OK — PDFs urbanísticos/fiscales |
| Sede electrónica | https://laacebeda.sedelectronica.es | OK (espublico gestiona) |
| Tablón anuncios | https://laacebeda.sedelectronica.es/board | OK — **vacío** (emptyRow) |
| Info tablón | https://laacebeda.sedelectronica.es/info.0 | OK — sin filas urbanísticas |
| SITCM WFS ámbitos | https://idem.comunidad.madrid/geoserver3/ows | OK |

## Proyectos / expedientes

- **CMS:** WordPress (sitemap XML accesible, tema The7)
- **Listado principal:** sección `/urbanismo/` con tres cronogramas de actuación (Casa de la Maestra, Manga Ganadera, Acondicionamiento Camino), cada uno con enlace a PDF de planos
- **Ordenanzas:** PDF ordenanza de construcción (2020) y ordenanzas fiscales de terrenos urbanos / ICO en `/ordenanzas-municipales/`
- **Noticias WP:** posts sobre vivienda protegida (IVIMA), bandos de limpieza de solares, BOCM presupuestos
- **Sede espublico:** tablón `/board` accesible pero sin filas publicadas (agosto 2026)
- **Planeamiento histórico:** 4 unidades de ejecución en SITCM (`UE-1 NORTE` … `UE-4 ANTIGUAS ESCUELAS`)

## Licencias de obra

- No hay dataset ni tablón con concesiones publicadas
- La página de urbanismo lista trámites (licencias mayores/menores, cédulas, primera ocupación, etc.) como información administrativa
- Ordenanzas fiscales ICO y ocupación de suelo vía vía pública disponibles en PDF
- Adapter devuelve páginas informativas de trámite + ordenanzas (`min_rows: 0` para concesiones reales)

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS SITCM `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='LA ACEBEDA'`
  - 4 features: UE-1 NORTE, UE-2 RONDA ESTE-NORTE, UE-3 RONDA ESTE-CENTRO, UE-4 ANTIGUAS ESCUELAS
  - Campo enlace: `DS_NOMB_AMB` (código + nombre sector)
  - Visor regional: https://www.madrid.org/cartografia/sitcm/html/visor.htm
- **Estrategia:** cargar todos los ámbitos SITCM como proyectos con polígono; enriquecer posts WP por matching de código UE en título
- **Limitaciones:**
  - Sin visor urbanístico propio del ayuntamiento
  - Cronogramas publican PDFs de planos sin coordenadas embebidas
  - Tablón sede vacío — sin expedientes IP actuales
  - SITCM solo cubre ámbitos de planeamiento aprobados (no licencias puntuales ni obras de embellecimiento)

## Limitaciones generales

- Tablón de anuncios sede sin contenido scrapeable
- Sin API JSON de expedientes
- PDFs de planos sin georreferencia directa
- Municipio muy pequeño (7 entradas BOCM) — poca actividad urbanística publicada online
- User-Agent identificable requerido; sin dependencia de LLM
