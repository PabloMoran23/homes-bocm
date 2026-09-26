# Guarromán — investigación portal ayuntamiento

**Municipio:** Guarromán (Jaén, Andalucía)  
**Slug:** `guarroman`  
**INE:** 23039  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.guarroman.es | **Operativa** — WordPress (tema CityGov) |
| Sede electrónica | https://guarroman.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://guarroman.sedelectronica.es/board | **Operativa** — ~8 filas vigentes (rotación) |
| Urbanismo (web) | https://www.guarroman.es/urbanismo/ | **Operativa** — PDFs planos + ordenanza polígono industrial |
| Ordenanzas urbanísticas | https://www.guarroman.es/transparencia-ayuntamiento-guarroman/informacion-institucional/normativa/ordenanzas-urbanisiticas/ | **Operativa** — 5 PDFs normativa |
| Registro instrumentos planeamiento | https://www.guarroman.es/registro-municipal-instrumentos-planeamiento/ | **Vacío** — sin documentos enlazados |
| Obras y Urbanismo (sede) | https://guarroman.sedelectronica.es/citizen-service/4b04d1fc-d511-4ec8-9239-4c3d2c05a3cc | **Informativa** — licencias urbanísticas |
| PBOM (tramitación) | https://pbomguarroman.es | **Protegida** — anti-bot / carga diferida |
| Portal transparencia sede | https://guarroman.sedelectronica.es/transparency | **Parcial** — carpeta «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (3 docs) vía AJAX/login |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Vera, Cártama, Guardo.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}`.
- **Paginación:** ~8 anuncios vigentes; rotación frecuente (empleo, padrones, arbitrios).

### Ejemplos urbanísticos históricos (tablón)

| Fecha | Expediente | Procedimiento | Descripción |
|-------|------------|---------------|-------------|
| 05/03/2026 | 631/2025 | Actuaciones Urbanísticas | Información pública calificación ambiental gasolinera/supermercado (pol. 37, ref. catastral 23039A037000510000QI) |
| — | — | Urbanismo | Anuncios de información pública de actuaciones urbanísticas (cuando vigentes) |

## Licencias de obra

- No hay dataset público de concesiones de licencia de obra con coordenadas.
- Página informativa «Licencias Urbanísticas» en sede (`citizen-service/...`) describe declaraciones responsables y trámites.
- Solicitudes vía catálogo `/dossier`; consulta de expedientes requiere identificación (`/expedientes`).
- El adapter incluye páginas informativas del tablón, trámites y ordenanzas.

## Proyectos / planeamiento

- **Tablón:** actuaciones urbanísticas, información pública (p. ej. calificación ambiental ASTROIL exp. 631/2025).
- **Ordenanzas web:** Normas Subsidiarias, edificación, habitabilidad, residuos construcción (PDFs en `wp-content/uploads`).
- **Urbanismo web:** ordenanza reguladora polígono industrial + 15 planos PDF (jul 2022).
- **PBOM:** nuevo Plan Básico de Ordenación Municipal en tramitación (LISTA); avance aprobado jul 2026; web pbomguarroman.es con protección anti-bot.
- **Normas Subsidiarias vigentes:** modificaciones puntuales publicadas en BOJA (p. ej. cambio de uso SAU, registro RAIU 9572).
- **BOJA:** 1 entrada histórica en pipeline; no re-parseada por el adapter.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - Sin visor urbanístico municipal público (ArcGIS, QGIS, etc.).
  - IDEAndalucía DERA WFS Sistema Urbano (`ideandalucia.es/services/DERA_g7_sistema_urbano/wfs`) — capas regionales sin enlace a código de expediente del ayuntamiento.
  - Planos PDF en `/urbanismo/` sin georreferencia ni servicio WMS/WFS asociado.
  - Tablón y transparencia: documentos PDF sin coordenadas.
- **Estrategia:** no hay fuente GIS pública enlazable a expedientes. El orquestador aplicará centroide municipio (38.182, -3.687) + jitter.
- **Limitaciones:**
  - Sin `geom_geojson` por proyecto.
  - PBOM web no accesible para scrape automatizado.
  - Carpeta transparencia urbanismo en sede requiere interacción AJAX.

## Limitaciones generales

- Tablón con pocos anuncios vigentes y predominio de empleo/padrones.
- Sin listado histórico público de licencias concedidas.
- Registro municipal de instrumentos de planeamiento vacío en web.
- PBOM en proceso de redacción; instrumento vigente son Normas Subsidiarias.

## Adapter implementado

- `municipio.adapters.guarroman:GuarromanAyuntamientoAdapter`
- Fuentes: tablón sede + ordenanzas urbanísticas (web) + planos urbanismo (web) + páginas informativas trámites.
