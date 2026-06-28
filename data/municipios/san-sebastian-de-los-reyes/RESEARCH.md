# San Sebastián de los Reyes — investigación portal ayuntamiento

**Municipio:** San Sebastián de los Reyes (Comunidad de Madrid)  
**Fecha:** 2026-06-21  
**BOCM regional (referencia):** 38 avisos

## Resumen

El ayuntamiento usa **Liferay** en la web corporativa (`www.ssreyes.org`) y la sede electrónica
(`sede.ssreyes.es`). Ambos dominios exigen la cookie `browser_verified=1` (anti-bot ligero) para
servir contenido HTML.

La información de **planeamiento** está publicada como páginas temáticas con PDFs en
`/documents/1678104/...`. No hay visor de expedientes urbanísticos individuales enlazados a
geometría.

## Fuentes identificadas

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| PGOU 2001 | `https://www.ssreyes.org/plan-general-de-ordenaci%C3%B3n-urbana-p.g.o.u.-` | Liferay + PDFs | Planos, normativa, memorias (~14 docs) |
| Planos PGOU | `https://www.ssreyes.org/planos` | PDFs | Planos estructuración/clasificación/ordenación |
| Desarrollos plan parcial | `https://www.ssreyes.org/desarrollos-urban%C3%ADsticos-mediante-plan-parcial` | Índice + subpáginas | Tempranales, Fresno Norte, Pilar de Abajo, Puente Cultural, PERI |
| Plan Especial La Marina | `https://www.ssreyes.org/plan-especial-de-la-marina` | Página informativa IP | Texto aprobación inicial (sin PDFs embebidos en crawl) |
| PERI | `https://www.ssreyes.org/plan-especial-de-reforma-interior-p.e.r.i.-` | PDFs (~9) | Documentación PERI |
| Planes especiales | `https://www.ssreyes.org/planes-especiales` | Índice | Enlaces a PE La Marina |
| Urbanismo / SIT | `https://www.ssreyes.org/sistema-de-informaci%C3%B3n-territorial-de-urbanismo` | Enlace geoportal | Visor Tecnogeo |
| Actuaciones urbanísticas (trámites) | `https://www.ssreyes.org/tr%C3%A1mites1/-/asset_publisher/.../id/2613627` | PDFs impresos | Declaraciones responsables, solicitudes licencia |
| Tablón sede | `https://sede.ssreyes.es/tabl%C3%B3n-de-anuncios` | Liferay Asset Search | **POST búsqueda devuelve 403** desde CI |
| Transparencia urbanismo | `https://transparencia.ssreyes.org/urbanismo` | HTML informativo | Contexto IP (p. ej. PE La Marina) |

### Subpáginas con documentación (crawl BFS)

- `https://www.ssreyes.org/tempranales` — 11 PDFs plan parcial
- `https://www.ssreyes.org/fresno-norte` — 2 PDFs
- `https://www.ssreyes.org/pilar-de-abajo` — 2 PDFs
- `https://www.ssreyes.org/puente-cultural` — 1 PDF

## Estructura técnica

- **CMS:** Liferay Portal 7.x (`com.liferay.*` portlets, `/documents/{groupId}/...` document library).
- **Anti-bot:** página intermedia que establece `browser_verified=1` (8 h); el adapter envía la cookie.
- **Tablón sede:** portlet `as_asac_asset_search_AssetSearchInstancePortlet` con categorías
  (Ayuntamiento SSR, Anuncio/Edicto). La búsqueda POST con `searchAssets` responde **403 Forbidden**
  desde el entorno del agente (posible WAF/CSRF adicional).
- **Trámites licencia:** solo formularios PDF descargables; no dataset de concesiones con dirección.

## Licencias

No hay listado público scrapeable de licencias concedidas con fecha y ubicación (sin paridad Madrid
capital). El adapter ingiere:

- PDFs de declaraciones responsables y solicitudes de licencia en la página de actuaciones urbanísticas
- Páginas informativas de trámites (tipo, sin `fecha_concesion`)

## Proyectos / expedientes

Documentos y páginas de planeamiento: PGOU, planes parciales por desarrollo, PERI, plan especial La
Marina (metadatos de página). Los PDFs usan URLs estables con UUID Liferay.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - **Visor municipal (Tecnogeo Citymap):**  
    `https://citymap.tecnogeows.com/user/100812377150920593660/map/PYbgc7dWp2V8Yt9yU7MmeF`  
    Consulta por parcela/dirección; `search.tecnogeows.com` sin API pública documentada para expedientes.
  - **WFS Comunidad de Madrid (SIT):** capa `sitcm:VPLA_V_AMBITO` en  
    `https://idem.comunidad.madrid/geoserver3/ows` — ámbitos de planeamiento con geometría GeoJSON.
    Consulta por `DS_MUNICIPIO ILIKE '%San Sebasti%'` + nombre de desarrollo (p. ej. Tempranales, Fresno).
- **Estrategia adapter:** tras extraer metadatos, `_fetch_geometry()` consulta WFS por palabras clave
  del título/URL de la página (Tempranales, Fresno Norte, etc.) y rellena `geom_geojson` cuando hay
  coincidencia.
- **Limitaciones:**
  - Sin enlace expediente↔polígono en el portal municipal
  - PERI, La Marina y PGOU genérico no devuelven polígono fiable por nombre en WFS
  - Tablón de licencias inaccesible por POST 403
  - Tecnogeo requiere JWT de sesión anónima (no estable para batch)

## Limitaciones generales

- Cookie `browser_verified` obligatoria en www y sede
- Tablón sede: búsqueda automatizada bloqueada (403)
- Sin coordenadas en listados de licencias
- PDFs sin georreferencia embebida

## Referencia adapters

- Liferay + cookie: `villaviciosa_de_odon.py`, `pinto.py`
- WFS CM planeamiento: `sector_geometry/resolvers_madrid.py` (patrón `VPLA_V_AMBITO`)
