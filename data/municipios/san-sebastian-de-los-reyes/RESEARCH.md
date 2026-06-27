# San Sebastián de los Reyes — investigación portal ayuntamiento

**Municipio:** San Sebastián de los Reyes (Comunidad de Madrid)  
**Fecha:** 2026-06-27  
**BOCM regional (referencia):** 38 avisos

## Resumen

El ayuntamiento usa **Liferay** en tres dominios:

| Dominio | Acceso scrape | Uso |
|---------|---------------|-----|
| `transparencia.ssreyes.org` | OK (HTML completo) | Planeamiento, PDFs `/documents/`, carpetas `folderId` |
| `sede.ssreyes.es` | OK | Tablón edictos locales, trámites licencia |
| `www.ssreyes.org` | Anti-bot (`browser_verified`) | No usado por el adapter |

## Fuentes identificadas

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Transparencia urbanismo | `https://transparencia.ssreyes.org/urbanismo` | Liferay + PDFs | Índice PGOU, CTSPGOU |
| PGOU 2001 | `.../plan-general-de-ordenación-urbana-p.-g.-o.-u.-2001` | Páginas + PDFs | Normativa, acuerdos |
| Planes parciales | `.../tempranales`, `fresno-norte`, `pilar-de-abajo` | PDFs (~15) | Documentación desarrollos |
| Plan Especial La Marina | `.../plan-especial-de-la-marina` | Carpetas Liferay | IP aprobación inicial 2026 |
| Acuerdos CTSPGOU | `.../acuerdos-de-la-comisión-técnica-de-seguimiento-del-pgou` | PDFs BOCM | Acuerdos comisión seguimiento |
| Planos PGOU | `.../planos` | PDFs | Planos ordenación |
| Tablón edictos sede | `https://sede.ssreyes.es/ayuntamiento-de-san-sebastián-de-los-reyes` | Asset Publisher | Edictos / IP (11+ anuncios) |
| Trámites licencia | `https://sede.ssreyes.es/procedimiento-de-solicitud-de-obra-por-tramitación-abreviada` | Páginas informativas | Impresos licencia |
| Visor urbanístico | `https://citymap.tecnogeows.com/user/100812377150920593660/map/PYbgc7dWp2V8Yt9yU7MmeF` | Tecnogeo Citymap | Consulta parcela (sin API batch) |

## Estructura técnica

- **CMS:** Liferay Portal 7.x (`com.liferay.*`, document library `/documents/{groupId}/{folderId}/...`).
- **Transparencia:** crawl BFS siguiendo enlaces `folderId=` y subpáginas web del área urbanismo (~100+ PDFs).
- **Sede edictos:** portlet Asset Publisher (`/-/asset_publisher/.../content/id/{id}`) con metadatos Vigencia y PDFs.
- **Anti-bot:** solo en `www.ssreyes.org`; el adapter usa `transparencia` + `sede`.

## Licencias

No hay dataset público de licencias concedidas con dirección/fecha (sin paridad Madrid capital). El adapter ingiere:

- Páginas informativas de trámites en sede (obra abreviada, declaración responsable)
- PDFs de impresos cuando están enlazados
- Edictos del tablón sede filtrados por palabras clave licencia

## Proyectos / expedientes

Documentos de planeamiento desde transparencia (PGOU, planes parciales, PERI, acuerdos CTSPGOU) más edictos de información pública en sede. URLs estables con UUID Liferay.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - **Visor municipal (Tecnogeo Citymap):**  
    `https://citymap.tecnogeows.com/user/100812377150920593660/map/PYbgc7dWp2V8Yt9yU7MmeF`  
    Consulta por parcela/dirección; requiere JWT de sesión, sin API REST pública estable.
  - **WFS Comunidad de Madrid (SIT):** capa `sitcm:VPLA_V_AMBITO` en  
    `https://idem.comunidad.madrid/geoserver3/ows` — ámbitos de planeamiento con GeoJSON.  
    Consulta: `DS_MUNICIPIO ILIKE '%San Sebasti%'` + `DS_NOMB_AMB ILIKE '%{desarrollo}%'`.
- **Estrategia adapter:** `_fetch_geometry()` consulta WFS por palabras clave del título/URL (Tempranales, Fresno, Pilar, etc.).
- **Limitaciones:**
  - Sin enlace expediente↔polígono en portal municipal
  - PERI, La Marina y documentos genéricos PGOU no devuelven polígono fiable por nombre
  - Tecnogeo no expone API documentada para batch
  - WFS CM puede fallar intermitentemente (reintentos en adapter)

## Limitaciones generales

- `www.ssreyes.org` bloqueado por verificación de navegador
- Tablón sede mezcla edictos administrativos con urbanismo; filtro por regex
- Sin geometría por expediente individual; geocode usa centroide WFS o jitter municipal
