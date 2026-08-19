# Gargantilla del Lozoya — investigación portal ayuntamiento

Municipio fusionado oficialmente como **Gargantilla del Lozoya y Pinilla de Buitrago** (Comunidad de Madrid).

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web principal (WP Elementor) | https://gargantillaypinilla.madrid | PGOU, ordenanzas, documentos, noticias |
| PGOU | https://gargantillaypinilla.madrid/plan-general-de-ordenacion-urbana/ | Exposición pública PGOU (TransferNow + PDFs) |
| Ordenanzas | https://gargantillaypinilla.madrid/ordenanzas/ | Ordenanzas fiscales y urbanísticas (PDFs BOCM) |
| Documentos municipales | https://gargantillaypinilla.madrid/documentos-municipales/ | Formularios licencia obra, DR obras |
| Portal legacy (Liferay) | https://www.gargantilla.es/urbanismo | Sección urbanismo (poca documentación scrapeable) |
| Sede electrónica | https://gargantillaypinilla.sedelectronica.es | espublico gestiona — tablón de anuncios (vacío) |
| Sede antigua | https://gargantillaypinilla.sedelectronica.es/ | Marcada como inactiva; la sede activa es la anterior |

## Cómo se listan expedientes / proyectos

- **PGOU:** página WordPress con enlace TransferNow (`envio-gpa.transfernow.net`) y PDFs locales (`/wp-content/uploads/PDF/varios/`).
- **Ordenanzas:** icon-box Elementor con enlaces directos a PDF (muchas publicadas en BOCM).
- **Noticias:** WP REST API `/wp-json/wp/v2/posts` — pocas entradas urbanísticas; la de construcción de recintos de biorresiduos (2026) es relevante.
- **Tablón sede:** HTML estático espublico; `<tbody>` con `emptyRow` (sin filas públicas al scrapear).
- **Sin visor de expedientes** ni listado Drupal/Joomla de actuaciones.

## Licencias de obra

- Formularios en `documentos-municipales`: `solicitud-licencia-obra.pdf`, `IMPRESO-DECLARACION-RESPONSABLE-OBRAS.pdf`.
- No hay listado público de licencias concedidas; solo trámites informativos.
- Ordenanza de tasas de licencias urbanísticas en página de ordenanzas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS Comunidad de Madrid SITCM `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='GARGANTILLA DEL LOZOYA Y PINILLA DE BUITRAGO'`.
- **Ámbitos:** 7 polígonos del PGOU (`POLÍGONO 1` … `POLÍGONO 7`) — sin visor web municipal; solo capa regional.
- **Estrategia:** descarga WFS por municipio; enriquecimiento por coincidencia de «polígono N» en título; filas `sit_wfs` con geometría directa.
- **Limitaciones:** sin ArcGIS/visor local; tablón y PDFs sin georreferencia; sede sin anuncios scrapeables; TransferNow no automatizable.

## Limitaciones generales

- Dos dominios web (`.madrid` nuevo + `.es` legacy Liferay) con contenido parcialmente duplicado.
- Sede espublico operativa pero tablón vacío.
- Sin API de expedientes; scrape determinista sobre WP REST + HTML.
- 4 entradas BOCM en cola regional (no re-parseadas).
