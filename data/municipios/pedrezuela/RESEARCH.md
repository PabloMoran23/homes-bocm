# Pedrezuela — investigación portal ayuntamiento

**Municipio:** Pedrezuela (`pedrezuela`)  
**Comunidad:** Comunidad de Madrid  
**Boletín:** BOCM (`bocm_count`: 9)

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (WordPress Genesis) | https://pedrezuela.info |
| Trámites / formularios PDF | https://pedrezuela.info/tramites/ |
| Urbanismo | https://pedrezuela.info/areas/urbanismo/ |
| Licencias de obras | https://pedrezuela.info/areas/urbanismo/licencias-de-obras/ |
| PGOU | https://pedrezuela.info/areas/urbanismo/plan-general-de-ordenacion-urbana/ |
| Proyectos municipales | https://pedrezuela.info/areas/urbanismo/actuaciones-municipales/ |
| Normas subsidiarias | https://pedrezuela.info/areas/urbanismo/normas-subsidiarias/ |
| Sede electrónica (espublico gestiona) | https://pedrezuela.sedelectronica.es |
| Tablón de anuncios | https://pedrezuela.sedelectronica.es/board/ |
| Portal transparencia sede | https://pedrezuela.sedelectronica.es/transparency |
| Catálogo trámites | https://pedrezuela.sedelectronica.es/dossier |

## Cómo se listan expedientes / proyectos

1. **Páginas urbanismo WordPress** — HTML estático con PDFs (PGOU avance 2025, ordenanzas, consulta previa, bulevar A-1, peatonalización centro histórico). WP REST API devuelve 401 (solo usuarios autenticados).
2. **Tablón sede** — HTML tabla Wicket/YUI en `/board/` con `preview-document/{uuid}`. A agosto 2026 predomina empleo público y presupuestos; entradas urbanísticas aparecen esporádicamente.
3. **Transparencia sede** — Sección «URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (0 documentos indexados en agosto 2026).
4. **Ámbitos SITCM** — WFS Comunidad de Madrid con 10 polígonos (SAU-1/2/3, UA-1..7).

No hay visor urbanístico propio del ayuntamiento ni dataset GeoJSON municipal.

## Cómo se publican licencias

- **Formularios PDF** en `/tramites/` y `/areas/urbanismo/`: obra mayor/menor, primera ocupación, ocupación vía pública, licencia actividad, piscinas, etc.
- **Tablón sede** — Concesiones/notificaciones cuando se publican (sin entradas de licencia visibles en agosto 2026).
- **Catálogo dossier** — Trámites informativos espublico (licencia obra mayor/menor, declaración responsable urbanística, etc.).
- No hay dataset abierto de licencias concedidas con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS SITCM: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='PEDREZUELA'`
  - Campos: `DS_NOMB_AMB` (SAU-1 COREPO, UA-3 LAS ERAS A, etc.), `DS_FIG_DES`
- **Estrategia:** Cargar los 10 ámbitos del municipio desde WFS; enriquecer por código SAU/UA en título; centroides en `geom_geojson`.
- **Limitaciones:**
  - No hay visor ArcGIS municipal ni enlace expediente→polígono en sede.
  - Tablón y páginas WP no traen geometría embebida.
  - WFS cubre ámbitos de planeamiento, no parcelas de licencias individuales.
  - Consulta de expedientes en sede requiere identificación Cl@ve.

## Limitaciones generales

- Sede espublico gestiona (Wicket/AJAX); sin API JSON del tablón.
- SSL sede: certificado con cadena intermedia; adapter usa `insecure_ssl: true`.
- WP REST API bloqueada; adapter hace crawl HTML de páginas urbanismo.
- PGOU en tramitación (avance aprobado diciembre 2025); documentación en PDF en web.

## Referencias de patrón

- **espublico gestiona sede:** El Molar, Venturada, San Agustín del Guadalix
- **WFS SITCM partial:** El Molar, Venturada, Paracuellos de Jarama
