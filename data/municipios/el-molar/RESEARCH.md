# El Molar — investigación portal ayuntamiento

**Municipio:** El Molar (`el-molar`)  
**Comunidad:** Comunidad de Madrid  
**Boletín:** BOCM (`bocm_count`: 20)

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (WordPress) | https://elmolar.org |
| Planificación Urbana | https://elmolar.org/ayuntamiento/areas-de-gobierno/planificacion-urbana-vivienda-e-infraestructuras/ |
| Documentación / formularios | https://elmolar.org/tramites/documentacion/ |
| Sede electrónica (espublico gestiona) | https://elmolar.sedelectronica.es |
| Tablón de anuncios | https://elmolar.sedelectronica.es/board/ |
| Portal transparencia sede | https://elmolar.sedelectronica.es/transparency |
| Catálogo trámites | https://elmolar.sedelectronica.es/dossier |
| Urbanismo transparencia | https://elmolar.sedelectronica.es/citizen-service/cb07ecfa-a5b4-4a85-9bc9-d133fc07a33f |
| WP REST API | https://elmolar.org/wp-json/wp/v2/posts |

## Cómo se listan expedientes / proyectos

1. **Noticias WordPress** — Publicaciones sobre PGOU (avance 2024, redacción contrato 2023), reurbanización C/ Almendro, obra Plaza Mayor, bandos de desbroce en parcelas, bulevar A-1, etc. API REST paginada (`/wp-json/wp/v2/posts`).
2. **Tablón sede** — HTML tabla Wicket/YUI en `/board/` con `preview-document/{uuid}`. A julio 2026 predomina empleo público; entradas urbanísticas aparecen esporádicamente.
3. **Transparencia sede** — Sección «URBANISMO y ACTIVIDADES» (`citizen-service/...`); navegación Wicket sin listado JSON público de expedientes.
4. **Ámbitos SITCM** — WFS Comunidad de Madrid con polígonos de suelo urbanizable (SAU-*) del municipio.

No hay visor urbanístico propio del ayuntamiento ni dataset GeoJSON municipal.

## Cómo se publican licencias

- **Formularios PDF** en `/tramites/documentacion/`: obra mayor/menor, primera ocupación, ocupación vía pública, licencia actividad, parcelación/segregación, etc.
- **Tablón sede** — Concesiones/notificaciones cuando se publican (actualmente sin entradas de licencia visibles).
- **Catálogo dossier** — Trámites informativos espublico (si están catalogados).
- No hay dataset abierto de licencias concedidas con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS SITCM: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='EL MOLAR'`
  - Campos: `DS_NOMB_AMB` (código ámbito, p. ej. SAU-24), `DS_FIG_DES`
- **Estrategia:** Cargar todos los ámbitos del municipio desde WFS; enriquecer por código SAU/UE en título; centroides en `geom_geojson`.
- **Limitaciones:**
  - No hay visor ArcGIS municipal ni enlace expediente→polígono en sede.
  - Tablón y noticias WP no traen geometría embebida.
  - WFS cubre ámbitos de planeamiento (SAU), no parcelas de licencias individuales.
  - El ayuntamiento no publica coordenadas de licencias de obra.

## Limitaciones generales

- Sede espublico gestiona (Wicket/AJAX); sin API JSON del tablón.
- SSL sede: certificado gestionado por proveedor; adapter usa `insecure_ssl: true`.
- PGOU en tramitación: documentación principal en noticias, no PDFs estructurados en web.
- Paginación WP: ~800 posts; adapter limita a 8 páginas (800 entradas).

## Referencias de patrón

- **espublico gestiona sede:** Pelabravo, El Berrueco (`board/` + `dossier`)
- **WFS SITCM partial:** Paracuellos de Jarama, El Berrueco
- **WP noticias urbanismo:** Fuente el Saz de Jarama
