# Algeciras — investigación portal ayuntamiento

## Fuentes base

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.algeciras.es | CMS SagaSuite: urbanismo, transparencia, trámites |
| Sede electrónica (nueva) | https://algeciras.sedelectronica.es | espublico gestiona: tablón, trámites, transparencia |
| Sede antigua (migración) | https://sede.algeciras.es | En mantenimiento; redirige a la nueva sede |
| Transparencia urbanismo | https://www.algeciras.es/es/ayuntamiento/transparencia/transparencia-en-materias-de-urbanismo-y-obras-publicas/ | PDFs PGOU, modificaciones, diligencias, estudios |
| Consulta / exposición pública | https://www.algeciras.es/es/ayuntamiento/transparencia/relaciones-con-los-ciudadanos-y-la-sociedad/ | Tab con documentos en consulta pública (PDFs) |
| Delegación urbanismo | https://www.algeciras.es/es/temas/urbanismo-y-vivienda/delegacion-de-urbanismo/ | Documentación PGOU histórica (PDFs en galería) |
| Tablón sede | https://algeciras.sedelectronica.es/board | Tabla HTML con `preview-document` (edictos) |
| Catálogo trámites | https://algeciras.sedelectronica.es/dossier | Enlaces `/catalog/t/...` (licencias, DR, planeamiento) |
| Urbanismo (info sede) | https://algeciras.sedelectronica.es/citizen-service/43207c42-4b23-454f-b860-8869daf9a041 | Páginas informativas de trámites |

## Cómo se listan expedientes / licencias

- **Proyectos / planeamiento:** principalmente PDFs enlazados desde transparencia urbanismo y la página de relaciones con la ciudadanía (consultas públicas). No hay listado JSON ni RSS; el adapter parsea enlaces `.pdf` en HTML SagaSuite (`/export/sites/algeciras/.galleries/...`).
- **Licencias concedidas:** no hay dataset histórico abierto. El tablón `/board` publica edictos puntuales (pocos urbanísticos en el scrape). Las licencias se tramitan por sede (`/dossier`); la consulta de expedientes propios requiere identificación (Cl@ve / certificado) en `/expedientes`.
- **Trámites web:** listado limitado en https://www.algeciras.es/es/ayuntamiento/tramites/ (p. ej. obra menor, plusvalías).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor urbanístico municipal: https://algeciras.enmapa.com/portada (Enmapa / cartografía PGOU; aviso legal de que no sustituye expedientes).
  - Catálogo metadatos: https://algeciras.enmapa.com/geonetwork
  - Agenda Urbana (indicadores, no expedientes): https://www.agendaurbanaalgeciras.es/visor-web/
- **Estrategia:** el visor Enmapa no expone en el entorno del agente un MapServer/WFS consultable por código de expediente (respuesta HTTP 403 sin sesión de navegador). Los PDFs del portal no incluyen geometría vectorial parseable de forma determinista.
- **Limitaciones:** sin enlace estable expediente → `objectId` GIS; el orquestador usará centroide municipal + jitter (`manifest.portal.config.centroid`).

## Limitaciones generales

- Migración de sede (2025): expedientes antiguos pueden no estar accesibles temporalmente.
- Delegación de urbanismo en web muestra “página en construcción” pero la galería PGOU sigue publicando PDFs.
- Tablón sede: volumen bajo de anuncios urbanísticos frente a transparencia web.
