# Colmenar del Arroyo — investigación portal ayuntamiento

## URLs base

| Fuente | URL | Tecnología |
|--------|-----|------------|
| Web municipal | https://www.colmenardelarroyo.es | PHP estático (tema CIFP) |
| Urbanismo y licencias | https://www.colmenardelarroyo.es/urbanismo.php | HTML + PDFs en `/gestor/descargas/` |
| Planos / callejero | https://www.colmenardelarroyo.es/planocallejero.php | Página informativa (sin visor GIS embebido) |
| Ordenanzas | https://www.colmenardelarroyo.es/ordenanzas.php | Sin PDFs urbanismo scrapeables |
| Punto información catastral | https://www.colmenardelarroyo.es/punto_informacion_catastral.php | Enlace RAT PDF |
| Sede electrónica | http://colmenardelarroyo.sedelectronica.es | espublico gestiona (eHome/Wicket) |
| Tablón de anuncios | http://colmenardelarroyo.sedelectronica.es/board | Tabla HTML (vacía al 2026-08) |
| Portal transparencia | http://colmenardelarroyo.sedelectronica.es/transparency | espublico (sin catálogo urbanismo scrapeable) |
| Catálogo trámites | http://colmenardelarroyo.sedelectronica.es/dossier | Timeout >70s desde CI |
| Visor SITCM CM | https://www.madrid.org/cartografia/sitcm/html/visor.htm | Referencia ámbitos UA-/AA-/S- |

## Proyectos / expedientes

- **SITCM WFS:** 47 ámbitos de planeamiento en capa `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='COLMENAR DEL ARROYO'` (UA-1…UA-35, AA-1…AA-11, S-1 LAS VIÑUELAS SUR).
- **Tablón sede:** sin elementos publicados («No se han encontrado elementos»).
- **Web municipal:** sin listado de expedientes en información pública ni PGOU; solo requisitos de trámites presenciales.
- **BOCM:** 4 entradas históricas en pipeline regional (no re-parseadas).

## Licencias

- No hay dataset público de concesiones ni consulta CONEX municipal.
- Formularios descargables en `urbanismo.php`: solicitud licencia de apertura (`gestor/descargas/apertura.pdf`), cambio de titularidad (`CambioTitularidad.pdf`).
- Trámites obra menor/mayor/primera ocupación documentados en HTML pero sin PDF directo en la página.
- Tablón sede vacío; sin licencias publicadas en anuncios.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS Comunidad de Madrid `https://idem.comunidad.madrid/geoserver3/ows` capa `sitcm:VPLA_V_AMBITO`, campo `DS_NOMB_AMB` (códigos UA-*, AA-*, S-*).
- **Estrategia:** ingestar los 47 ámbitos SITCM como proyectos con polígono WGS84; enriquecer títulos de tablón/PDF que mencionen código de ámbito.
- **Limitaciones:** sin visor urbanístico municipal propio (`planocallejero.php` sin ArcGIS/iframe mapa). Transparencia y `/dossier` no scrapeables de forma fiable. Tablón sin coords. Licencias solo formularios sin georef.

## Limitaciones generales

- `/dossier` no responde en tiempo razonable desde entornos CI.
- Tablón actualmente vacío.
- Licencias: solo páginas informativas y formularios PDF (no concesiones).
- Paridad proyectos depende principalmente de ámbitos SITCM regional.
