# Manzanilla — investigación portal ayuntamiento

**Municipio:** Manzanilla (Huelva, Andalucía)  
**INE:** 21051  
**BOCM/BOJA:** 1 aviso histórico (`boja`)

## URLs base y páginas semilla

| Fuente | URL | Notas |
|--------|-----|-------|
| Web municipal | https://www.ayuntamientodemanzanilla.es | OpenCMS Saga Suite (Diputación Huelva) |
| Urbanismo | https://www.ayuntamientodemanzanilla.es/es/servicios/urbanismo/ | Concejalía María Godoy Padilla |
| PGOU | https://www.ayuntamientodemanzanilla.es/es/pgou/ | Planeamiento vigente, catálogos PDF |
| Ordenanzas | https://www.ayuntamientodemanzanilla.es/es/ayuntamiento/ordenanzas/ | Incl. ORDENANZA_EDIFICACION.pdf |
| Transparencia PGOU | https://www.ayuntamientodemanzanilla.es/es/gobierno-abierto/portal-transparencia/resultados-de-transparencia/Esta-publicado-el-Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan.-00040/ | Indicador DPH cumplido |
| Sede electrónica | https://manzanilla.sedelectronica.es | espublico gestiona |
| Tablón anuncios | https://manzanilla.sedelectronica.es/board/ | **Vacío** (emptyTable) |
| Catálogo trámites | https://manzanilla.sedelectronica.es/dossier/ | 19 trámites urbanismo/licencias |
| SITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | PGOU aprobado definitivamente 2014 |

## Cómo se listan expedientes / proyectos

- **PGOU:** página web con secciones de texto (planeamiento vigente, usos, clasificación suelo) y PDFs en `/export/sites/manzanilla/es/.galleries/pgou/`.
- **Catálogos:** `catolomanzanilla1.pdf`, `catalogomanzanilla2.pdf` (elementos protegidos).
- **Normativa:** ordenanza de edificación y otras en galería ordenanzas.
- **Tablón sede:** sin filas publicadas actualmente.
- **No hay** listado de expedientes urbanísticos individuales ni visor de información pública estructurado.

## Cómo se publican licencias

- **Tablón sede:** vacío; canal previsto para edictos de licencias.
- **Catálogo trámites** (`/dossier/`): licencias de obra, actividad, ocupación, comunicaciones previas — solo fichas de trámite, sin histórico de concesiones.
- **No hay** dataset ni tabla pública de licencias concedidas (similar a otros municipios pequeños con espublico).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - PGOU web: mapas/planos referenciados en transparencia pero solo como PDF o texto HTML, sin GeoJSON/WFS.
  - SITUA (Junta de Andalucía): visor regional de planeamiento general; no expone geometría por expediente vía API pública consultable.
  - No hay visor ArcGIS municipal, WFS ni datos abiertos georreferenciados.
- **Estrategia:** sin `_fetch_geometry`; el orquestador aplicará centroide municipal + jitter.
- **Limitaciones:** PGOU aprobado 2014 (BOJA 2018/135 cumplimiento); cartografía solo en PDF; sede sin publicaciones activas.

## Limitaciones generales

- Web requiere User-Agent estándar (curl sin UA devuelve vacío).
- Tablón sede vacío → licencias como páginas informativas de trámites.
- `/dossier` sin barra final provoca redirect loop; usar `/dossier/`.
- SSL sede con certificado gestionado por espublico (`insecure_ssl: true` en config).
