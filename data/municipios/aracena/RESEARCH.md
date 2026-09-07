# Aracena — investigación portal ayuntamiento

**Municipio:** Aracena (`aracena`)  
**Provincia:** Huelva, Andalucía  
**INE:** 21006  
**BOJA:** 1 expediente en BOCM histórico

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://www.aracena.es/es/ | CMS SAGA (Diputación de Huelva) |
| Urbanismo | https://www.aracena.es/es/areas-tematicas/Urbanismo/ | Índice urbanismo |
| PGOU | https://www.aracena.es/es/areas-tematicas/Urbanismo/PGOU.html | Memoria, EIA, normativa (PDFs galería) |
| PMVS | https://www.aracena.es/es/areas-tematicas/Urbanismo/pmvs.html | Plan Municipal Vivienda y Suelo 2022-2025 |
| Ordenanza placas solares | https://www.aracena.es/es/areas-tematicas/Urbanismo/placassolares.html | BOP 2020 |
| Redes | https://www.aracena.es/es/areas-tematicas/Urbanismo/redes.html | Ordenanza despliegue redes |
| Modelos oficiales | https://www.aracena.es/es/areas-tematicas/Urbanismo/modelosoficiales.html | DR y comunicación previa |
| Sede electrónica | https://aracena.sedelectronica.es | espublico gestiona |
| Tablón de anuncios | https://aracena.sedelectronica.es/board/ | Wicket HTML, 10 filas visibles |
| Urbanismo (sede) | https://aracena.sedelectronica.es/citizen-service/b6354b5b-50a3-4882-9ce1-9bb82bb2ffe8 | Info trámites licencias/DR |
| Transparencia | https://aracena.sedelectronica.es/transparency | Portal transparencia sede |

## Cómo se listan expedientes / proyectos

- **Web SAGA:** documentos urbanísticos en galerías estáticas bajo `/export/sites/aracena/es/.galleries/` (PGOU, PMVS, ORDENANZAS, REDES, MODELOSOFICIALES). HTML con enlaces directos a PDF.
- **Tablón sede:** tabla Wicket con columnas documento, expediente, procedimiento, categoría, descripción, fecha. Paginación AJAX (Wicket); primera página suele ser personal/subvenciones. Edictos urbanísticos aparecen esporádicamente.
- **Consulta expedientes:** `/expedientes` requiere identificación electrónica; no hay listado público indexable.

## Cómo se publican licencias

- No hay dataset ni listado histórico de licencias concedidas.
- Concesiones puntuales en tablón de anuncios (cuando se publican).
- Trámites informativos en sede: licencias urbanísticas, declaraciones responsables, autorizaciones.
- Modelos oficiales (comunicación previa urbanística 2022) en web municipal.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - SITUA Junta de Andalucía (`situadifusion`): visor PGOU provincial sin API por expediente ni enlace código→polígono.
  - Web municipal: sin visor urbanístico ni datos abiertos georreferenciados.
  - Diputación de Huelva (`diphuelva.es`): sin WFS/ArcGIS enlazable a expedientes de Aracena.
  - Sede espublico: expedientes tras login, sin geometría pública.
- **Estrategia:** centroide municipal (37.8936, -6.5603) + jitter en orquestador `geocode`.
- **Limitaciones:** solo PDFs de planeamiento/ordenanzas; tablón sin coords; SSL de www.aracena.es requiere `insecure_ssl` en algunos entornos.

## Limitaciones técnicas

- Certificado SSL de `www.aracena.es` puede fallar verificación estricta → `insecure_ssl: true`.
- Tablón sede: paginación Wicket AJAX; el adapter scrapea la primera página + fuentes web estables.
- Sin licencias históricas públicas → filas informativas de trámites en `licencias.jsonl`.

## Patrón CMS

SAGA Diputación de Huelva (`com.saga.sagasuite.theme.diputacion.huelva.base`) + espublico gestiona sede. Similar a otros municipios onubenses (Bornos Cádiz usa patrón distinto EPICSA; Aracena sigue plantilla Dip. Huelva).
