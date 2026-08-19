# Jaén — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `jaen` |
| Provincia | Jaén |
| CCAA | Andalucía |
| Boletín | BOJA (`boletin_source_id: boja`) |

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.aytojaen.es | Portal corporativo (gestor JSP) |
| Sede electrónica STA | https://sede.aytojaen.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_HOME | Tablón, catálogo trámites |
| Tablón anuncios/edictos | https://sede.aytojaen.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all | Dataset JS `dataset_PTS2_TABLON` (~321 filas) |
| Catálogo trámites | https://sede.aytojaen.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO | Dataset JS `dataset_CATSERV` (~110 trámites) |
| Ordenanzas urbanismo | https://sede.aytojaen.es/portal/sede/se_contenedor1.jsp?seccion=s_ldoc_d10_v1.jsp&codbusqueda=1255&language=es | PDFs ordenanzas fiscales y urbanísticas |
| Instrumentos planeamiento | https://www.aytojaen.es/portal/p_14_distribuidor1.jsp?language=es&codResi=1&codMenuPN=4&codMenu=260 | Enlace a planes vigentes |
| Planes vigentes (ZIP) | https://planesdeordenacion.aytojaen.es/vigentes/ | PGOU 1996, PEPRI 1996, adaptación LOUA 2009 |
| Avance PGOM 2025 | https://planesdeordenacion.aytojaen.es/PGOM/index.html | Frameset con menú PDF (memoria, cartografía, ordenación) |
| Avance POU / POU-CH | https://planesdeordenacion.aytojaen.es/POU/index.html | Planes de ordenación en tramitación |
| Transparencia urbanismo | https://transparencia.aytojaen.es/7medioambiente | Enlaces a instrumentos y exposición pública |

## Cómo se listan expedientes / proyectos

1. **Tablón STA**: HTML con array JSON embebido `var dataset_PTS2_TABLON = [...]`. Campos: `dboid`, `descriptionProc`, `externString`, `pubDateIni`, `remitent.description`. Filas de Gerencia Municipal de Urbanismo (licencias, PGOU, UE, proyectos de urbanización).
2. **Catálogo STA**: `dataset_CATSERV` con trámites de licencias (12302, 12303, 10620 comunicación previa, etc.) — páginas informativas, no concesiones individuales.
3. **Avance PGOM**: `menu2.html` lista ~50 PDFs de memoria y cartografía del nuevo PGOM 2025.
4. **Planes vigentes**: directorio Apache con 3 archivos ZIP del planeamiento consolidado.

## Cómo se publican licencias

- **Tablón STA**: edictos y notificaciones de licencias de obra (p. ej. «LICENCIA DE OBRA CON PROYECTO…») publicados por Área de Disciplina Urbanística / GMU.
- **Catálogo**: trámites electrónicos de solicitud (no listado de concesiones históricas).
- No hay dataset abierto de licencias con coordenadas ni geometría parcelaria.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - `planesdeordenacion.aytojaen.es/PGOM/mapas.html` — placeholder estático «Visor de planos»; cartografía solo en PDF.
  - Diputación de Jaén WMS/WFS (`ide.dipujaen.es`) — excluye explícitamente Jaén y Linares (>50.000 hab.).
  - Web municipal «Mapa web» en urbanismo — mapa corporativo sin capas de expedientes ni API ArcGIS/WFS.
  - No se encontró MapServer/FeatureServer/WFS con enlace a expediente o ref. catastral.
- **Estrategia:** sin fuente GIS consultable; el orquestador aplicará centroide municipal + jitter.
- **Limitaciones:** cartografía en PDF/ZIP sin georreferencia machine-readable; sede STA sin geometría; SSL autofirmado en `planesdeordenacion.aytojaen.es` (requiere `insecure_ssl`).

## Limitaciones

- Certificado SSL inválido en subdominio `planesdeordenacion.aytojaen.es`.
- Algunas URLs del gestor web (`codbusqueda=1255`) devuelven HTTP 500 intermitente.
- Exposición pública (`codbusqueda=1475`) sin listado documental scrapeable (solo enlaces a sede).
- Sin visor urbanístico interactivo público para Jaén capital.
