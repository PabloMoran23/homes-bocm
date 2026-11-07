# Carcaixent — investigación portal ayuntamiento

## Fuentes base

| Recurso | URL | Contenido |
|---------|-----|-----------|
| Web corporativa (Drupal, Digital Value) | https://www.carcaixent.es/es | Sección **Territori / Urbanismo**, plano urbano, RSS |
| Plano urbano + PDFs históricos | https://www.carcaixent.es/es/pagina/plano-urbano | Plànols 2010/2017, documentación PGOU |
| Noticias urbanismo | https://www.carcaixent.es/es/noticia-novetats-pagina/territori | Modificaciones puntuales PGOU, cesiones EVHA (PDFs) |
| Plan movilidad | https://www.carcaixent.es/es/pagina/general/plan-movilidad-urbana-sostenible | PMUS |
| RSS municipal | https://www.carcaixent.es/es/rss.xml | Últimas noticias (pocas entradas) |
| Sede espublico gestiona | https://carcaixent.sedelectronica.es/info | Trámites, instancias |
| Tablón anuncios | https://carcaixent.sedelectronica.es/board | Edictos Wicket (filas HTML parseables) |
| Catálogo trámites | https://carcaixent.sedelectronica.es/dossier | Licencias/DR/comunicaciones (requiere sesión cookies) |
| Transparencia | https://carcaixent.sedelectronica.es/transparency/ | Carpeta «URBANISME, OBRES PÚBLIQUES I MEDI AMBIENT» (88 docs, carga AJAX) |
| Visor GV | https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz | Inventario SU/SUZ Comunitat Valenciana |

Sin boletín regional asociado en cola (`bocm_count: 0`).

## Cómo se listan expedientes

- **Planeamiento sectorial:** ICV `terramapas.icv.gva.es` servicio WFS `ms:InventarioSuSuz`, filtro espacial bbox municipal + `cod_ine_mun=46083` (12 polígonos sectoriales: GALIANA GOLF, MOTILLA, etc.).
- **Información pública / PGOU:** páginas Drupal bajo `/es/noticia-novetats-pagina/territori/*` con PDFs de exposición pública y acuerdos OATM.
- **Tablón:** `board` publica edictos en tabla HTML (`class_name`, `class_folderCode`, …); en la muestra (nov 2026) predominan personal/subvenciones; entradas urbanísticas aparecen esporádicamente.
- **Transparencia urbanismo:** carpeta con 88 documentos; despliegue vía Wicket AJAX sin URLs REST públicas de carpeta (no scrapeable sin JS).

## Licencias

No hay listado histórico público de concesiones. El catálogo de sede expone trámites:

- Declaración responsable / comunicación urbanística
- Solicitud de licencia o autorización urbanística
- Recepción de obras de urbanización
- Modificación/renuncia de licencia

URLs `catalog/t/<uuid>` extraídas de `dossier` tras semilla de cookies en `/info`.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS ICV `0702_Planeamiento` → capa `ms:InventarioSuSuz`, campo `cod_ine_mun=46083`, geometría `ms:msGeometry` GML → GeoJSON WGS84.
- **Estrategia:** ingestar sectores SU/SUZ del inventario estatal; enriquecer filas Drupal/tablón por coincidencia de tokens sectoriales (`UE`, `SECTOR`, nombre PP).
- **Limitaciones:** CQL_FILTER del servicio no filtra correctamente por INE (se usa bbox + post-filtro). Transparencia y expedientes puntuales no enlazan polígono. Tablón sin georreferencia directa.

## Limitaciones generales

- Catálogo `dossier` puede redirigir en bucle sin cookies de sesión.
- Visor transparencia urbanismo requiere navegación AJAX.
- RSS municipal con pocas entradas recientes.
- Drupal sin JSON:API público.
