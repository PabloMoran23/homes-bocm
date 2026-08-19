# Serranillos del Valle — investigación portal ayuntamiento

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.serranillosdelvalle.es |
| Normativa / PGOU | https://serranillosdelvalle.es/normativa/ |
| Documentos (TownPress lsvr_document) | https://serranillosdelvalle.es/documents/ |
| Tablón WP (categoría) | https://serranillosdelvalle.es/categoria/tablon-de-anuncios/ |
| Sede electrónica eAdmin | https://sede.serranillosdelvalle.es/eAdmin/Sede.do |
| Tablón sede | https://sede.serranillosdelvalle.es/eAdmin/Tablon.do?action=verAnuncios&tipoTablon=1 |
| Trámites sede | https://sede.serranillosdelvalle.es/eAdmin/Registrar.do?action=inicioPortalTramites |
| Formulario licencia urbanística | https://sede.serranillosdelvalle.es/Formularios/Sol-Lic-Urbanist-2022.pdf |
| Declaración responsable obras | https://sede.serranillosdelvalle.es/Formularios/DEC-RESP-OBRAS.pdf |

**Nota:** `serranillosdelvalle.sedelectronica.es` (espublico) devuelve «Sede Electrónica Indeterminada» — no operativa. La sede activa es `sede.serranillosdelvalle.es/eAdmin`.

## CMS y formato de datos

- **Web:** WordPress con tema **TownPress** (LSVR).
- **Documentos PGOU:** custom post type `lsvr_document`, expuesto en REST API `/wp-json/wp/v2/lsvr_document` (~30 entradas: memoria informativa, memoria de ordenación, normas urbanísticas por capítulos). Cada página enlaza PDFs en `/wp-content/uploads/2025/11/NORMAS-URBANISTICAS-*.pdf`.
- **Tablón sede:** HTML tabular eAdmin (`Tablon.do`), filas con `verAnuncio&id=<hex>`, periodo de publicación y enlace `abrirOriginal('<token>')` → `ValidarDocumento.do`.
- **Tablón WP:** posts en categoría `tablon-de-anuncios` (convocatorias, bases); sin expedientes urbanísticos relevantes salvo duplicados del sede.

## Proyectos / expedientes

- **PGOU / normas urbanísticas:** 30 documentos `lsvr_document` (avance PGOU 2025, capítulos normas urbanísticas).
- **Tablón sede:** 43 anuncios; urbanismo relevante: «DOCUMENTACIÓN AVANCE. CERTIFICADO APROBACIÓN» (sep 2025).
- **SITCM:** 22 ámbitos de planeamiento (planes parciales SUZ-R.*, sectorización SUZ-NS.*, etc.).

## Licencias

- No hay listado público de concesiones de licencia con coordenadas.
- Trámites informativos en sede (formularios PDF licencia urbanística y declaración responsable).
- El tablón sede no contiene licencias de obra publicadas en el periodo analizado.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='SERRANILLOS DEL VALLE'`
  - Campos: `DS_NOMB_AMB` (nombre ámbito, p. ej. `SUZ-R.1 LA DIEZMARÍA`), `DS_FIG_DES` (figura)
  - Visor: https://www.madrid.org/cartografia/sitcm/html/visor.htm
- **Estrategia:** importar los 22 polígonos SITCM como proyectos de planeamiento; enriquecer filas de tablón/PDF si el título contiene código SUZ-* o nombre de ámbito.
- **Limitaciones:** licencias y expedientes puntuales sin enlace GIS; tablón mayoritariamente no urbanístico; geometría de licencias individuales no disponible.
