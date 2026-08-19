# Nuevo Baztán — investigación portal ayuntamiento

**Municipio:** Nuevo Baztán (`nuevo-baztan`)  
**Comunidad:** Comunidad de Madrid  
**Boletín:** BOCM (`bocm_count`: 7)

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (WordPress Divi) | https://ayto-nuevobaztan.es |
| Urbanismo | https://ayto-nuevobaztan.es/urbanismo/ |
| Documentación y trámites | https://ayto-nuevobaztan.es/documentacion-y-tramites/ |
| Actualidad / noticias | https://ayto-nuevobaztan.es/actualidad/ |
| Sede electrónica (espublico gestiona) | https://nuevobaztan.sedelectronica.es |
| Tablón de anuncios | https://nuevobaztan.sedelectronica.es/board/ |
| Catálogo trámites | https://nuevobaztan.sedelectronica.es/dossier |
| Urbanismo sede | https://nuevobaztan.sedelectronica.es/citizen-service/ef8a54f8-49a6-43c3-af0a-d9b64b4142d4 |
| Portal transparencia (eadministracion) | https://transparenciaayto-nuevobaztan.eadministracion.es/transparencia/funcionamiento/urbanismo |
| Planes urbanísticos transparencia | https://transparenciaayto-nuevobaztan.eadministracion.es/transparencia/funcionamiento/urbanismo/planes-urbanisticos-y-estudios-de-impacto-ambiental |
| Sitemaps WP | https://ayto-nuevobaztan.es/post-sitemap.xml, wpfd_file-sitemap.xml |

## Cómo se listan expedientes / proyectos

1. **Noticias WordPress** — Publicaciones sobre urbanización Eurovillas, obras canal Isabel II, acondicionamiento aparcamientos zona escolar, recepción urbanizaciones, etc. REST API bloqueada por Kadence Security; adapter usa sitemaps `post-sitemap*.xml` + scrape HTML (`article:published_time`).
2. **Documentos WPFD** — Formularios y normativa en `wpfd_file-sitemap.xml` (declaración responsable urbanística, solicitud licencia, autoliquidaciones ICIO/tasas obras).
3. **Tablón sede** — HTML tabla Wicket en `/board/` con `preview-document/{uuid}`. A agosto 2026 una entrada visible (decreto alcaldía, no urbanismo).
4. **Portal transparencia eadministracion** — Sección «Planes urbanísticos y estudios de impacto ambiental» sin listado documental estructurado en HTML público.
5. **Ámbitos SITCM** — WFS Comunidad de Madrid: 6 polígonos (UA-1..UA-4, UE-1, UE-2).

No hay visor urbanístico propio del ayuntamiento ni dataset GeoJSON municipal.

## Cómo se publican licencias

- **Formularios PDF** en `/documentacion-y-tramites/` y wpfd: declaración responsable urbanística, solicitud licencia urbanística (Ley 1/2020), primera ocupación, paneles solares, autoliquidación ICIO/tasas obras.
- **Tablón sede** — Concesiones/notificaciones cuando se publican (actualmente sin entradas de licencia visibles).
- **Catálogo dossier** — Trámites informativos espublico.
- No hay dataset abierto de licencias concedidas con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS SITCM: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO LIKE 'NUEVO BAZT%'`
  - Campos: `DS_NOMB_AMB` (UA-1..UA-4, UE-1, UE-2), `DS_CLAS_SUE`
- **Estrategia:** Cargar ámbitos del municipio desde WFS; enriquecer por código UA/UE en título; centroides en `geom_geojson`.
- **Limitaciones:**
  - No hay visor ArcGIS municipal ni enlace expediente→polígono en sede.
  - Tablón y noticias WP no traen geometría embebida.
  - WFS cubre ámbitos de planeamiento, no parcelas de licencias individuales.
  - El ayuntamiento no publica coordenadas de licencias de obra.

## Limitaciones generales

- Sede espublico gestiona (Wicket/AJAX); sin API JSON del tablón.
- SSL sede: adapter usa `insecure_ssl: true`.
- WP REST API bloqueada (`itsec_rest_api_access_restricted`); scrape HTML vía sitemaps.
- Portal transparencia eadministracion sin documentos indexados en HTML scrapeable.
- Paginación sitemap posts: adapter filtra por slug/título urbanístico antes de fetch individual.

## Referencias de patrón

- **espublico gestiona sede:** El Molar, Pelabravo (`board/` + `dossier`)
- **WFS SITCM partial:** El Molar, Paracuellos de Jarama
- **WP Divi + wpfd:** municipios con download manager y sitemap wpfd
