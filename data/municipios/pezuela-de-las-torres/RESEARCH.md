# Pezuela de las Torres — investigación portal ayuntamiento

**Municipio:** Pezuela de las Torres (`pezuela-de-las-torres`)  
**Comunidad:** Comunidad de Madrid  
**Boletín:** BOCM (`bocm_count`: 3)

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (WordPress Divi) | https://pezueladelastorres.es |
| Plan general de urbanismo | https://pezueladelastorres.es/plan-general-de-urbanismo/ |
| Sede electrónica (espublico gestiona) | https://pezueladelastorres.sedelectronica.es |
| Tablón de anuncios | https://pezueladelastorres.sedelectronica.es/board/ |
| Portal transparencia sede | https://pezueladelastorres.sedelectronica.es/transparency/ |
| Catálogo trámites (dossier) | https://pezueladelastorres.sedelectronica.es/dossier |
| Transparencia urbanismo (sede) | https://pezueladelastorres.sedelectronica.es/transparency/eea024da-381f-4703-8fac-404b38b6a46c/ |

## Cómo se listan expedientes / proyectos

1. **Noticias WordPress** — REST API `/wp-json/wp/v2/posts` accesible. Entradas sobre PGOU, obras municipales (Cuatro Calles, Mayor Norte), bandos de desbroce.
2. **Página PGOU** — HTML Divi con PDFs de consulta vecinal previa al avance (2024-2025).
3. **Tablón sede** — HTML Wicket/YUI en `/board/` con `preview-document/{uuid}`. Agosto 2026: PEI Canal Isabel II (arteria El Pozo de Guadalajara), anuncios BOCM.
4. **Transparencia sede** — Sección «URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (47 documentos indexados).
5. **Ámbitos SITCM** — WFS Comunidad de Madrid con 8 polígonos UA-1..UA-8 (normas subsidiarias 1988).

No hay visor urbanístico propio del ayuntamiento ni API JSON del tablón.

## Cómo se publican licencias

- **Tablón sede** — Concesiones/notificaciones cuando se publican (sin entradas de licencia de obra visibles en agosto 2026).
- **Catálogo dossier** — Trámites espublico (licencia obra mayor/menor, etc.); página muy lenta (>45s) y contenido cargado por AJAX.
- **Sede principal** — Trámites identificados con Cl@ve; sin dataset abierto de licencias concedidas.
- No hay formularios PDF de licencias en la web municipal (a diferencia de municipios con `/tramites/`).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS SITCM: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='PEZUELA DE LAS TORRES'`
  - Campos: `DS_NOMB_AMB` (UA-1 C/MAYOR Y C/NUEVA, UA-2, …), `DS_CLAS_SUE`, `DS_DOCU` (NORMAS SUBSIDIARIAS)
- **Estrategia:** Cargar los 8 ámbitos UA desde WFS; enriquecer por código UA en título; centroides en `geom_geojson`.
- **Limitaciones:**
  - Los polígonos WFS aparecen georreferenciados cerca del centro de Madrid (~40.42, -3.17) en lugar del término municipal (~40.75, -3.28) — posible error de datos en SITCM; el orquestador puede usar `centroid` del manifest + jitter si se detecta geometría fuera del municipio.
  - No hay visor ArcGIS municipal ni enlace expediente→polígono en sede.
  - Tablón y noticias WP no traen geometría embebida.
  - WFS cubre ámbitos de planeamiento (NNSS 1988), no parcelas de licencias individuales.

## Limitaciones generales

- Sede espublico gestiona (Wicket/AJAX); `/dossier` responde con latencia alta.
- SSL sede: adapter usa `insecure_ssl: true`.
- PGOU en tramitación (avance en consulta sectorial CM); documentación en PDF en web y noticias.
- Consulta de expedientes en sede requiere identificación Cl@ve.

## Referencias de patrón

- **espublico gestiona sede:** Pedrezuela, Venturada, El Molar
- **WFS SITCM partial:** Pedrezuela, Navalagamella, Pelayos de la Presa
