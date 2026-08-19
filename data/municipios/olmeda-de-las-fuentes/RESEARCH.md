# Olmeda de las Fuentes — investigación portal ayuntamiento

**Municipio:** Olmeda de las Fuentes (`olmeda-de-las-fuentes`)  
**Comunidad:** Comunidad de Madrid  
**Boletín:** BOCM (`bocm_count`: 6)

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (CMS propio) | https://olmedadelasfuentes.es |
| Área urbanismo | https://www.olmedadelasfuentes.es/areas/urbanismo-mantenimiento-e-imagen-urbana |
| PGOU | https://www.olmedadelasfuentes.es/pgou |
| Normativa urbanismo | https://olmedadelasfuentes.es/normativa-de-urbanismo |
| Proyectos obra municipal | https://www.olmedadelasfuentes.es/proyectos-de-obra-municipales--1 |
| Catálogo trámites | https://olmedadelasfuentes.es/catalogo-de-tramites |
| Trámites | https://olmedadelasfuentes.es/tramites |
| Sede electrónica (espublico gestiona) | https://olmedadelasfuentes.sedelectronica.es |
| Tablón de anuncios | https://olmedadelasfuentes.sedelectronica.es/board |
| Portal transparencia sede | https://olmedadelasfuentes.sedelectronica.es/transparency |
| Catálogo trámites sede | https://olmedadelasfuentes.sedelectronica.es/dossier |
| SIT Comunidad de Madrid | https://www.comunidad.madrid/servicios/urbanismo-medio-ambiente |

## Cómo se listan expedientes / proyectos

1. **Web municipal** — CMS ASP.NET con páginas estáticas y PDFs en `/Ficheros/Documentos/` (PGOU: memoria, normas urbanísticas, catálogo bienes protegidos, planos JPG). Noticias de actualidad en categoría «Urbanismo» (p. ej. plan parcial SUS-02).
2. **Tablón sede** — HTML Wicket/YUI en `/board/` con enlaces `preview-document/{uuid}`. A agosto 2026 pocos anuncios urbanísticos visibles en portada; licencias en transparencia.
3. **Transparencia sede** — Sección «6. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (~102 documentos). Incluye resoluciones de licencia urbanística (p. ej. DECRETO 2025-0305, expediente 215/2025).
4. **Ámbitos SITCM** — WFS Comunidad de Madrid con 12 polígonos (AA-1..4, AUNI-1, SUS-1..4).

No hay visor urbanístico propio del ayuntamiento ni API JSON de expedientes.

## Cómo se publican licencias

- **Formularios PDF** en catálogo de trámites: modelo licencia urbanística LU, declaración responsable urbanística DR, gestión RCD.
- **Transparencia sede** — Resoluciones y decretos de licencia cuando se publican (preview-document).
- **Tablón sede** — Anuncios y edictos cuando se publican.
- **Catálogo dossier sede** — Trámites informativos espublico (acceso lento; timeout frecuente).
- No hay dataset abierto de licencias concedidas con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS SITCM: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='OLMEDA DE LAS FUENTES'`
  - Campos: `DS_NOMB_AMB` (AA-1, SUS-2, AUNI-1, etc.), `DS_FIG_DES`
- **Estrategia:** Cargar los 12 ámbitos del municipio desde WFS; enriquecer por código AA/SUS/AUNI en título; centroides en `geom_geojson`.
- **Limitaciones:**
  - No hay visor ArcGIS municipal ni enlace expediente→polígono en sede.
  - Tablón y páginas web no traen geometría embebida.
  - WFS cubre ámbitos de planeamiento PGOU, no parcelas de licencias individuales.
  - Consulta de expedientes en sede requiere identificación Cl@ve.

## Limitaciones generales

- Sede espublico gestiona (Wicket/AJAX); sin API JSON del tablón.
- `/dossier` puede responder muy lento (>30 s).
- Transparencia requiere navegación AJAX para listar todos los documentos urbanismo.
- PGOU aprobado definitivamente (publicado en SIT desde 2015).

## Referencias de patrón

- **espublico gestiona sede:** Pedrezuela, Valdeolmos-Alalpardo, Venturada
- **WFS SITCM partial:** Pedrezuela, Boadilla del Monte, Paracuellos de Jarama
