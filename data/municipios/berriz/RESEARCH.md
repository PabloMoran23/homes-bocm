# Berriz — INE 48019, Bizkaia

Revisión: 2026-11-09. Adaptador de cobertura parcial de proyectos e instrumentos
urbanísticos del Ayuntamiento de Berriz, País Vasco.

## Descubrimiento y fuentes oficiales

La portada https://www.berriz.eus redirige al sitio municipal en euskera. El menú
se carga por JavaScript, pero su inventario público SharePoint se puede consultar
sin sesión en:
https://www.berriz.eus/es-ES/_api/web/lists/getByTitle('Menu%20Segundo%20Nivel')/items?$select=Title,Link&$top=5000
Desde «Urbanismo» se descubre:
https://www.berriz.eus/es-ES/Servicios/Urbanismo/Paginas/default.aspx
Esta página enlaza las secciones siguientes, comprobadas con HTTP 200:

- `expedientes-exposicion-publica.aspx`: inventario implementado, con documentos
  PDF concretos y agrupados por encabezado de expediente.
- `normativa-urbanistica-en-vigor.aspx`: remite al Registro de Planeamiento
  Urbanístico de Bizkaia, buscador por municipio e instrumento:
  https://www.bizkaia.eus/es/planeamiento-urbanistico-buscador?p_p_id=IYBIWPUC_INSTANCE_CadYBlTy6tfn&p_p_lifecycle=0&p_p_state=normal&p_p_mode=view
  No se incorpora ese registro: no se afirma cobertura de todo el planeamiento vigente.
- `pgou-2023.aspx`: explica las seis fases del PGOU y enlaza diagnóstico y avance.
  No se convierte cada fase descrita en un proyecto ni se afirma aprobación definitiva.
- `PlanGeneraldeOrdenacionUrbana.aspx`: enlaza un Word «Plan Territorial Parcial»;
  no se interpreta ese enlace aislado como PGOU aprobado de Berriz.

También se localizó el catálogo oficial de datos de planeamiento:
https://www.opendatabizkaia.eus/es/catalogo/planeamiento-urbanistico-berriz
El índice de búsqueda anuncia datos globales 2023–2026. No se usa como fuente de
proyectos: las estadísticas globales no equivalen a expedientes. El intento de API
CKAN en `/api/3/action/package_show?id=planeamiento-urbanistico-berriz` devolvió 404.

## Fuente implementada y semántica

https://www.berriz.eus/es-ES/Servicios/Urbanismo/Paginas/expedientes-exposicion-publica.aspx

Se extraen dos expedientes reales del inventario comprobado:

- Proyecto básico de bifamiliarización del caserío «Gomendio-Etxebarria»: proyecto,
  planos y anuncio de información pública (tres PDF).
- Estudio de Detalle de las parcelas nº 36 (U.E.I-1) y 38 de Eitua Industrialdea:
  expediente y anuncio de aprobación inicial e información pública (dos PDF).

La ordenanza de división de caseríos, con tres documentos, se excluye porque es
una norma general, no un proyecto físico o instrumento localizado. El anuncio
acompaña al expediente y no genera una entidad adicional. Los enlaces se extraen
cada vez del inventario; no hay lista fija de proyectos. Cada documento conserva
su título, URL, página de procedencia y SHA-256 de la descarga real. El ID de cada
instrumento deriva de su título, independiente del orden de los enlaces. Los
duplicados idénticos se consolidan y los conflictos producen error.

`fase: información pública` refleja la clasificación municipal, no una licencia
concedida ni la vigencia efectiva del plazo. La etiqueta de aprobación inicial
se conserva en el título del documento de Eitua. No se extraen fechas del contenido
PDF: `fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan nulas.
Los prefijos 20261019 y 20260924 de los archivos no se convierten en fechas legales.
Los PDF se descargan y validan por su cabecera; no se interpretan automáticamente.

La página es una lista estática de bloques HTML SharePoint, sin paginación activa
observada. El parser revisa controles de navegación y falla ante paginación, en vez
de aceptar una primera página incompleta. No recorre noticias, contratación, sede,
licencias ni archivo histórico. Cambios de marcado, ausencia de proyectos, enlaces
a documentos inesperados o pérdida de documentación sustantiva producen error.
La actualización vuelve a leer la instantánea completa; no implica histórico de
expedientes retirados. Las tipologías distintas a rehabilitación en información
pública y estudios de detalle quedan fuera del alcance actual.

## Geometría

geometry_status: unavailable

No se ha verificado una geometría vectorial asociada a estos expedientes. Los
planos se retienen como documentos y no se vectorizan. Sin coordenadas, centroides
ni desplazamientos artificiales: `geocode.jitter_missing: false` y
`publication_ready: false`. `schedule.enabled: false`; `licencias.enabled: false`.

## Validación y evidencia local

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Tres pruebas `unittest` comprueban agrupación/deduplicación, exclusión de ordenanza,
fechas nulas, IDs estables, errores por cambios/paginación y resolución del manifest.
La extracción real usa `load_manifest` y `load_portal_adapter`, con el guard de
entidades compartido, y escribe `evidence/proyectos.jsonl` y
`evidence/validation.json`. Los HTML explorados y los cinco PDF descargados quedan
bajo `evidence/`, incluidos los cuerpos usados por el adaptador en `captures/`.
Son evidencia local, no archivos fuente para incorporar al repositorio.
