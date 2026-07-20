# Salamanca — investigación portal ayuntamiento

**Municipio:** Salamanca (Salamanca, Castilla y León)  
**Slug:** `salamanca`  
**Boletín:** BOCYL (`bocyl`, 20 entradas en CSV)

## URLs base y páginas semilla

| Fuente | URL | Tecnología | Contenido |
|--------|-----|------------|-----------|
| Portal urbanismo | https://www.aytosalamanca.es/urbanismo-vivienda-y-obras | Liferay | Sección urbanismo, anuncios recientes |
| Planes en tramitación | https://www.aytosalamanca.es/urbanismo-vivienda-y-obras/planes-tramitacion | Liferay (h2 + enlace `/w/`) | ~16 expedientes activos (PGOU, convenios, estudios de detalle) |
| Anuncios urbanismo | https://www.aytosalamanca.es/anuncios?category=39289&delta=50 | Liferay (`slm-anuncio`) | Anuncios IP, aprobaciones, licencias |
| Sede STA tablón | https://www.aytosalamanca.gob.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=TABLON_EDICTOS | T-Systems STA | JSON embebido `metadata_TABLON_EDICTOS_LISTADO` (~85 filas) |
| Sede STA catálogo | https://www.aytosalamanca.gob.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO | STA + `dataset_CATSERV` | 23 trámites `STA_AMB_URBANISMO` (licencias, planeamiento) |
| Instrumentos gestión | https://www.aytosalamanca.es/w/instrumentos-de-gestión-urbanística | Liferay | Trámites informativos (formularios PDF) |
| Transparencia urbanismo | https://www.aytosalamanca.es/transparencia/urbanismo-obras-publicas-y-medioambiente | Liferay | Enlaces PGOU, convenios, normativa |

## Expedientes / proyectos

- **Planes en tramitación:** listado estático con `<h2 class="h5">` y enlace a página de contenido `/w/...`.
- **Anuncios urbanismo:** tarjetas `slm-anuncio` con fecha en español, título y enlace `/w/...`.
- **Tablón edictos:** tabla DataTables con metadata JSON en HTML (fecha, descripción con `linkHref`, categoría). Pocas entradas de urbanismo puro; mayoría plenos/presupuestos.
- **Catálogo sede:** trámites de urbanismo como páginas informativas (`DETALLE=<dboid>`).

No hay visor público de expedientes urbanísticos individuales (el acceso `EXPEDIENTES_FULL` requiere Cl@ve/certificado).

## Licencias

- No hay dataset público de licencias concedidas (como Madrid Open Data).
- **Tablón:** avisos puntuales de licencia ambiental (categoría Policía administrativa).
- **Catálogo STA:** trámites informativos (licencia obra mayor, demolición, declaración responsable, etc.) — no concesiones.
- **Anuncios:** alguna licencia de uso excepcional publicada como anuncio IP.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor PGOU: https://gis.geovincles.com/clients/viewer/salamanca/visor.php (GeoVincles / Google Maps)
  - Enlace desde portal: https://www.aytosalamanca.es/w/visor-pgou-1
  - GIS edificios ITE mencionado en portal (sin API documentada)
- **Estrategia:** el visor muestra capas del PGOU por sector (SU-NC, SUNC, etc.) pero no expone WMS/WFS/ArcGIS REST accesible ni campo de enlace a expediente. Los títulos de anuncios incluyen códigos de sector parseables (`SU-NC-47`, `SUNC-15`) pero no hay endpoint público para consultar polígono por código.
- **Limitaciones:** sin API GIS enlazable; geometría dependerá de geocode (centroide municipio + jitter) en el orquestador.

## Limitaciones

- Expedientes completos solo con autenticación en sede STA.
- Tablón con pocas entradas de urbanismo (mayoría administrativa).
- Licencias: solo trámites informativos + anuncios puntuales, no registro histórico.
- Sin geometría programática desde el portal.
