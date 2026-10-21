# Melilla — investigación portal ayuntamiento

## URLs base y semillas

| Fuente | URL |
|--------|-----|
| Portal web | https://www.melilla.es/melillaportal |
| Urbanismo (menú) | https://www.melilla.es/melillaportal/contenedor.jsp?seccion=s_lcont_d1_v4.jsp&codbusqueda=245 |
| Planeamiento Urbanístico | `contenido=13911` (Urbanismo en Red + PDF instrumentos vigentes) |
| PGOU documentos | `contenido=8547` (s_fdoc_d4_v1, ~70 PDFs) |
| Plan Especial Puerto | `contenido=23991` |
| Revisión PGOU | `contenido=31211` |
| Sede electrónica STA | https://sede.melilla.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_HOME |
| Tablón edictos | `PAGE_CODE=PTS2_TABLON&KEY=all` — `var dataset_PTS2_TABLON` (~1850 filas JSON) |
| Catálogo trámites | `PAGE_CODE=CATALOGO` — `var dataset_CATSERV` |
| Transparencia urbanística | https://sede.melilla.es/melillaPortal/transparencia/ (`codMenu=308`) |
| BOME | https://bomemelilla.es/ (boletín oficial; no integrado en adapter) |

## Listado de expedientes / planeamiento

- **Portal EADmin:** páginas `s_fdoc_d4_v1` / `s_fdes_d4_v1` con enlaces a `RecursosWeb/DOCUMENTOS/*.pdf`. El PGOU publica planos, normas, modificaciones y publicaciones BOME como PDFs sueltos (títulos genéricos tipo «Acuerdo», «Parte N»).
- **Planeamiento:** sección «Instrumentos de Ordenación Vigentes» con PDF consolidado (11/11/2020) y enlace al visor externo.
- **Sede STA tablón:** tabla JavaScript con `descriptionProc`, `pubDateIni`, `remitent`, `tablon` (categoría). La mayoría es normativa general y actas; pocos anuncios DGVU/urbanismo.
- **Catálogo STA:** trámites telemáticos DGVU (`PR2.03.10.*`: licencias de obra, demolición, segregación, cédula urbanística, etc.) — páginas informativas, no concesiones publicadas.

## Licencias de obra

No hay listado público de licencias concedidas (con fecha y dirección) comparable a Madrid. Fuentes disponibles:

1. Catálogo sede — trámites «Licencia de obra mayor/menor», «Comunicación previa», etc. (DGVU / DGA).
2. Tablón — escasos edictos con palabra «licencia» en normativa fiscal/ordenanzas.
3. Trámites informativos en portal (ruina, segregaciones, demolición, calificación).

El adapter devuelve filas de **catálogo + tablón** (trámites y anuncios), no concesiones individuales georreferenciadas.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** Visor «Urbanismo en Red» en https://urbithings.com/Melilla.maps (programa FEMP/red.es; manual PDF en portal). Cloudflare; sin endpoint WFS/ArcGIS/GeoJSON documentado ni enlace expediente→polígono en HTML público.
- **Estrategia:** No hay query determinista por código de expediente. El orquestador usará centroide municipio (`centroid` en manifest) + jitter.
- **Limitaciones:** PDFs sin georreferencia; visor SPA sin API REST accesible desde el agente; Melilla es ciudad autónoma única (sin capa CCAA estándar tipo ICV/IDEM).

## Limitaciones generales

- Tablón muy grande (~30s descarga) y dominado por normativa/actas parlamentarias.
- Codificación portal a veces `latin-1`.
- Sin boletín regional en `ccaa_history` (`bocm_count: 0`); BOME es fuente paralela no scrapeada aquí.
- SSL sede: flag `sede_insecure_ssl` por compatibilidad con otros adapters STA.
