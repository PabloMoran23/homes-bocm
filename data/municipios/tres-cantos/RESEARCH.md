# Tres Cantos — investigación portal ayuntamiento

## Sitio oficial

- **Web principal:** https://web.trescantos.es (WordPress / Elementor, redirige desde www.trescantos.es)
- **Sede electrónica:** https://sede.trescantos.es (eAdmin Java, tablón y trámites)
- **Tablón de anuncios:** https://sede.trescantos.es/eAdmin/Tablon.do?action=verAnuncios&tipoTablon=1
- **Detalle anuncio:** `Tablon.do?action=verAnuncio&id=<hash>` (tabla con Descripción, Fechas, GRUPO, Documento PDF)
- **Urbanismo (publicaciones WP):**
  - PGOU: https://web.trescantos.es/publicacion/plan-genera-ordenacion-urbana/
  - Planes parciales: https://web.trescantos.es/publicacion/planes-parciales/
  - Planes especiales: https://web.trescantos.es/publicacion/planes-especiales/
  - Proyectos urbanización: https://web.trescantos.es/publicacion/proyectos-de-urbanizacion/
  - Estudios de detalle: https://web.trescantos.es/publicacion/estudios-de-detalle/
- **Licencias urbanísticas (trámite informativo):** https://web.trescantos.es/tramite/licencias-urbanisticas/
- **Acceso IP urbanismo:** https://web.trescantos.es/tramite/acceso-a-la-informacion-publica-archivos-y-registros-de-urbanismo/

## Formato y acceso

| Fuente | Formato | Acceso |
|--------|---------|--------|
| Publicaciones urbanismo (WP) | HTML + PDFs en `/contenido/urbanismo/` | Público, scrapeable |
| Tablón sede (eAdmin) | HTML tabla listado + detalle por id | Público; puede bloquear IPs datacenter |
| Trámites licencia | Páginas informativas WP | Público (tramitación vía sede con certificado) |
| WP REST API custom types | No expuesto (`tramite`, `publicacion` → 404) | No disponible |

## Licencias

- No hay listado público de concesiones con coordenadas (paridad Madrid geo no disponible).
- Anuncios de licencia/urbanismo en **tablón sede** cuando se publican (GRUPO Anuncios, Urbanismo).
- Página informativa de trámites: `/tramite/licencias-urbanisticas/` con documentación PDF (`contenido/fondo-documental/l_lu.pdf`).

## Proyectos / expedientes

- **Publicaciones WP:** PGOU, planes parciales/especiales, proyectos de urbanización y estudios de detalle con PDFs agrupados por sección (h3/h4).
- **Tablón sede:** edictos, información pública, acuerdos urbanísticos.
- Expedientes individuales en `/publicacion/estudio-de-detalle-para-la-ordenacion-de-la-parcela-rc-30/` etc.

## Limitaciones

- `sede.trescantos.es` puede resetear conexión TLS desde IPs de cloud/datacenter (bloqueo WAF/firewall).
- Tablón solo muestra anuncios vigentes; histórico requiere scraping acumulativo.
- Sin API REST para custom post types de WordPress.
- Licencias sin `lat`/`lon`/`distrito` en fuentes públicas.

## Estrategia adapter

1. Scrape determinista de publicaciones urbanismo (PDFs en `/contenido/urbanismo/`).
2. Intento de tablón sede (`verAnuncios` + `verAnuncio`) con fallback silencioso si inaccesible.
3. Páginas informativas de trámites de licencia urbanística.
