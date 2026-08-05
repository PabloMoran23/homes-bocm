# Soto del Real — investigación portal ayuntamiento

Municipio: **Soto del Real** (`soto-del-real`)  
Provincia: Madrid | CCAA: Comunidad de Madrid | Boletín: BOCM (13 entradas)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web institucional | https://www.ayto-sotodelreal.es | WordPress Divi + Yoast SEO |
| Urbanismo y licencias | https://www.ayto-sotodelreal.es/urbanismo-y-licencias/ | Sección principal; enlaces a planeamiento y recepción urbanizaciones |
| Planeamiento urbanístico | https://www.ayto-sotodelreal.es/planeamiento-urbanistico/ | NNSS vigentes + planos PDF (clasificación, estructura, sectores) |
| Planos de ordenación | https://www.ayto-sotodelreal.es/planos-de-ordenacion/ | PO-1…PO-14 (calificación y gestión) |
| PSOU (avance) | https://www.ayto-sotodelreal.es/plan-sostenible-de-ordenacion-urbana/ | Memoria, normativa, estudios DIE, formulario consultas |
| Licencias y DR | https://www.ayto-sotodelreal.es/licencias-y-declaraciones-responsables/ | Información trámites (sin listado de concesiones) |
| Solicitud actividades | https://www.ayto-sotodelreal.es/urbanismo-y-licencias/solicitud-actividades/ | Formulario licencia actividades |
| Sede electrónica | https://sedesotodelreal.eadministracion.es/ | eAdmin (Maggioli/add4u) — trámites y tablón |
| Tablón eAdmin | https://sedesotodelreal.eadministracion.es/eAdmin/Tablon.do?action=verAnuncios | Tablón digital (vacío en HTML estático; sin filas `verAnuncio`) |
| WP REST API | https://www.ayto-sotodelreal.es/wp-json/wp/v2/posts | Noticias con IP/urbanismo (requiere User-Agent) |

## Cómo se listan expedientes / proyectos

1. **WordPress páginas estáticas**: botones/enlaces a PDFs de planeamiento (NNSS, planos PO-*, memorias PSOU). Extracción por `href="...pdf"`.
2. **WordPress noticias**: REST API `/wp-json/wp/v2/posts` — anuncios de información pública, modificaciones NNSS, recepción urbanizaciones, avance PSOU.
3. **SITCM WFS** (Comunidad de Madrid): capa `sitcm:VPLA_V_AMBITO` filtrada por `DS_MUNICIPIO='SOTO DEL REAL'` — 42 ámbitos (UA-*, IA-*) con polígonos.
4. **Sede eAdmin tablón**: estructura estándar add4u (`Tablon.do?action=verAnuncios` + POST `referenciaBusqueda`), pero **sin anuncios publicados** en el momento de la investigación (HTML sin filas).

## Cómo se publican licencias

- **No hay dataset abierto** de concesiones individuales (sin GeoJSON de licencias como Madrid capital).
- Trámites informativos en web (solicitud actividades, licencias y declaraciones responsables).
- Sede eAdmin permite presentación telemática pero el tablón de anuncios está vacío.
- El adapter devuelve páginas informativas de trámites + formularios (patrón Pozuelo/El Molar).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS SITCM: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='SOTO DEL REAL'`
  - Campo enlace: `DS_NOMB_AMB` (códigos UA-*, IA-*)
  - Visor regional: https://www.madrid.org/cartografia/sitcm/html/visor.htm
- **Estrategia:** cargar todos los ámbitos del municipio desde WFS; enriquecer proyectos cuyo título contenga código UA/IA o nombre de ámbito (ILIKE).
- **Limitaciones:**
  - No hay visor municipal propio con enlace a expediente.
  - PDFs de planeamiento sin georreferencia embebida.
  - Tablón sede vacío → licencias sin coordenadas propias.
  - Dropbox externo para NORMAS_URBANISTICAS.pdf (no scrapeado).

## Limitaciones generales

- Sede eAdmin: tablón y catálogo de trámites no exponen datos en HTML estático (posible renderizado JS/CiudadaNET).
- WP REST API bloquea peticiones sin User-Agent (403).
- Sin listado público de licencias concedidas con dirección/coords.
- Provincia en `queue.yaml` aparece como "Soto del Real" (dato del claim); manifest usa Madrid.

## Patrón CMS

WordPress Divi + sede **eAdmin** (eadministracion.es) — similar a Los Molinos, Valdilecha, El Boalo. Geometría vía SITCM WFS regional (patrón estándar municipios CM).
