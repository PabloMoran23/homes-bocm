# Ponteareas — investigación portal ayuntamiento

Municipio: **Ponteareas** (`ponteareas`) — Galicia, provincia Pontevedra.  
INE: **36042**. Sin boletín asociado en cola (`bocm_count: 0`).

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://portal.ponteareas.gal/ | WordPress / accesos directos (Plan Xeral Ordenación, taboleiro). **Certificado SSL roto** (`SSL_ERROR_SYSCALL`) desde el entorno del agente. |
| Sede electrónica | https://ponteareas.sedelectronica.gal/ | espublico gestiona (Wicket/YUI). |
| Taboleiro de anuncios | https://ponteareas.sedelectronica.gal/board | Tabla HTML con preview-document (Galician labels). |
| Catálogo trámites | https://ponteareas.sedelectronica.gal/dossier | 17+ trámites urbanísticos (licencias, comunicaciones, certificados). |
| Transparencia | https://ponteareas.sedelectronica.gal/transparency | Sección **7. URBANISMO, OBRAS PÚBLICAS E MEDIO AMBIENTE** (~64 docs). |
| SIOTUGA inventario | https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=36042 | PGOM + documentación normativa (`query_document.php` clases 13/14/16). |
| SIOTUGA estado | https://siotuga.xunta.gal/siotuga/urb?lang=es_ES | PGOM adaptado LOUG (aprobación 2021-09-30). Enlace WMS por concello. |
| Visor IDEG | https://ideg.xunta.gal/portalsix/apps/webappviewer/… | Visor ArcGIS Xunta (localización REAL 36860 Ponteareas). |
| Visor PBA | https://mapas.xunta.gal/visores/pba/ | Cartografía autonómica de planeamiento. |
| DOG PGOM 2021 | https://www.xunta.gal/dog/Publicados/2021/20211013/AnuncioG0532-041021-0001_es.html | Aprobación definitiva PGOM. |
| DOG MP01 2025 | https://www.xunta.gal/dog/Publicados/2025/20251106/AnuncioG0765-291025-0001_es.html | Modificación puntual EQ DEP 21 / centro de saúde. |

## Expedientes / proyectos

- **Ayuntamiento:** no hay visor de expedientes urbanísticos propio ni API JSON. El tablón publica anuncios con número de expediente en columna «Expediente» pero solo enlace a PDF (`preview-document`).
- **Xunta / SIOTUGA:** PGOM vigente (2021) con inventario documental (4 docs clase «xeral», más desarrollo/histórico). Tramitación autonómica de **MP01** (2025).
- **Transparencia sede:** PDFs urbanismo accesibles vía árbol espublico (no crawlado en v1; SIOTUGA cubre instrumentos principales).
- **Listado adapter:** metadatos DOG + SIOTUGA + anuncios del tablón filtrados por keywords urbanismo/licencias.

## Licencias

- **No** hay dataset ni tablón de licencias concedidas con fecha, dirección o coordenadas.
- Catálogo sede: licencias de obra, urbanísticas, comunicaciones previas (CP-0010…), terrazas, vaos, certificados urbanísticos, etc.
- Estrategia adapter: páginas informativas de trámites (`sede_tramite`).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - SIOTUGA: celda WMS por INE 36042 (documento de capacidades / cartografía PGOM a escala municipal).
  - IDEG ArcGIS Web App (Xunta) y visor PBA: consulta cartográfica, sin enlace determinista expediente tablón → `objectId`.
  - Proyecto EDUSI/iCarto (2019–2020): callejero SIG municipal; no expuesto como WFS público en la web del ayuntamiento.
- **Estrategia:** inventario normativo y anuncios sin polígono por fila; el orquestador aplica centroide municipal (`manifest.config.centroid`) + jitter en `geocode`. No se implementa query WMS SIOTUGA en v1 (sin código de sector estable en filas del tablón).
- **Limitaciones:** tablón solo PDF; portal corporativo inaccesible por SSL; SIOTUGA requiere cookie de sesión + `token` POST; geometría por expediente de obra no publicada.

## Limitaciones técnicas

- Sede espublico: calentar sesión con `info.0` para `/dossier`; el tablón `/board` debe fetcharse **sin** cookie jar (redirect loop si se reutiliza sesión Wicket).
- `portal.ponteareas.gal`: certificado/hosting inestable — usar sede como `base_url`.
- SIOTUGA `query_document.php` devuelve `tokenIncorrecto` sin cookie jar previo en inventario.
- `sync_supabase`: requiere `SUPABASE_DB_URL` en entorno CI/agente.
