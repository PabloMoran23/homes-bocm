# Los Marines — investigación portal ayuntamiento

Municipio: **Los Marines** (`los-marines`), provincia Huelva, Andalucía. Boletín: BOJA (1 entrada).

## URLs base y páginas semilla

| Fuente | URL | Tipo |
|--------|-----|------|
| Web municipal | https://www.losmarines.es | SAGA/OpenCMS (Alhambra) |
| Urbanismo | https://www.losmarines.es/es/areas-tematicas/urbanismo/ | Área temática |
| PGOU | https://www.losmarines.es/es/areas-tematicas/urbanismo/pgou/ | PDFs planeamiento (memorias, planos) |
| Sede electrónica | https://sede.losmarines.es | GSede OpenCMS (Guadaltel) |
| G·TABLÓN | https://sede.losmarines.es/moad/Gtablon_web-moad/index.htm?codOrganismo=048_TA | Tablón anuncios RichFaces |
| SITUA | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=21048 | Planeamiento general Junta de Andalucía |
| Portal Dip. Huelva | https://pdc.diphuelva.es/P2104800D | Contratación pública (no urbanismo) |
| Transparencia | https://www.losmarines.es/es/gobierno-abierto/portal-transparencia/ | Indicador PGOU publicado |

**Nota:** `losmarines.sedelectronica.es` devuelve página genérica "seleccione su sede"; la sede activa es `sede.losmarines.es`. `www.losmarines.es` requiere `insecure_ssl: true` (certificado inválido en CI).

## Expedientes / proyectos

1. **PGOU (web municipal):** 10 PDFs en galería OpenCMS (`/export/sites/losmarines/es/.galleries/Publicaciones-Oficiales/PGOU/`): memorias (introducción, ordenación, normas urbanísticas, catálogo protección), planos territorio/clasificación, núcleo calificación-gestión, protección patrimonial, PORN y PRUG Sierra de Aracena.
2. **G·TABLÓN:** Tablón Guadaltel en sede; actualmente 1 anuncio visible (Plan de Empleo 2026, no urbanismo). Sin API JSON; parseo HTML de celdas `idBandejaAnuncios`.
3. **SITUA:** PGOU aprobado definitivamente (BOJA 2013, expediente CP-068/20004). Consulta regional vía visor Junta de Andalucía; sin listado de expedientes individuales municipales.
4. **Consulta expedientes:** Requiere autenticación en sede GSede; no hay listado público de expedientes urbanísticos.

## Licencias de obra

- **Sin listado histórico** de licencias concedidas en portal público.
- Área **URBANISMO** en catálogo de trámites GSede (sede electrónica).
- G·TABLÓN puede publicar edictos de licencia (histórico escaso en municipio pequeño).
- Adapter devuelve páginas informativas de tablón + trámites (patrón Bornos/Cóin).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - PGOU cartografía en PDF (raster, no GeoJSON/WFS).
  - SITUA/VITUA Junta de Andalucía: planeamiento digitalizado regional, sin WFS/ArcGIS REST enlazable por código de expediente municipal.
  - Portal Diputación Huelva (`pdc.diphuelva.es`): contratación, sin capas urbanísticas GIS.
  - G·TABLÓN: solo PDFs de anuncios, sin coordenadas.
- **Estrategia:** No aplicable; orquestador usará centroide municipio + jitter.
- **Limitaciones:** Sin visor urbanístico municipal; PGOU solo PDF; municipio en Parque Natural Sierra de Aracena (autorizaciones ambientales adicionales).

## Limitaciones técnicas

- Web municipal `www.losmarines.es`: certificado SSL inválido → `insecure_ssl: true`.
- Sede `sede.losmarines.es`: certificado válido, accesible sin flag.
- G·TABLÓN RichFaces con sesión; pocas filas actualmente.
- Municipio pequeño (~300 hab.); publicaciones urbanísticas limitadas al PGOU histórico.
