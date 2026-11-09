# Cortegana — Huelva — INE 21025

Investigación y ejecución: 9 de noviembre de 2026. Se revisaron el contrato
`municipio/adapters/portal.py`, el cargador de manifests, el registro y los
adaptadores/manifests de Chipiona y Hernani. Solo se añaden los cuatro archivos
solicitados; la evidencia queda local y excluida del control de versiones.

## Descubrimiento y elección de fuente

- Ayuntamiento: https://www.cortegana.es/es/areas-tematicas/urbanismo/
- Ficha municipal: https://www.cortegana.es/es/areas-tematicas/urbanismo/pgou/
  La ficha muestra «P.G.O.U» y fecha editorial 07/04/2015, pero ningún documento.
  No se convierte esa ficha vacía en un proyecto ni se interpreta la fecha como
  aprobación. La verificación TLS falló con requests tanto con su CA por defecto
  como con el almacén del sistema. Únicamente para inspeccionar y capturar esas
  dos páginas se desactivó la verificación; el adaptador mantiene TLS verificado.
- La sede https://cortegana.sedelectronica.es/info.0 ofrece trámites urbanísticos:
  una declaración responsable o formulario no acredita una licencia concedida.
- Inventario oficial seleccionado, de la Junta de Andalucía:
  https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf
  Se inspeccionaron el formulario y sus scripts DataTables. La opción «Planes
  urbanísticos y territoriales aprobados» consulta por POST
  https://ws132.juntadeandalucia.es/situadifusion/pages/figuras.jsf con
  `codigos=21025`, `iDisplayStart`, `iDisplayLength=8`, `sEcho`, `iColumns=8`.
  El endpoint funciona sin sesión previa. Se contrastan provincia HUELVA y
  municipio CORTEGANA en cada fila, evitando Cortegada y Cortegana de Badajoz.

## Cobertura y resultados reales

Dos instrumentos del inventario actual de **planeamiento general aprobado**:

| ID SITUA | Figura y objeto de la ficha | Fecha de aprobación literal | Documentos únicos |
| --- | --- | --- | --- |
| 10606 | NNSS - Normas Subsidiarias Municipales; 1981 | 29/07/81 | 44 |
| 37291 | PAP - Procedimiento de Adaptación Parcial; Adaptación Parcial a la LOUA | 30/03/12 | 20 |

No se fijan estos registros ni cantidades en el scraper: proceden de la respuesta
viva. Las fichas usan `documentosCompartir.jsf?` con parámetros de consulta
codificados en base64, formato comprobado con la función «Compartir url» del
portal y con una sesión nueva. Cada registro conserva su enlace a la ficha,
identificador, figura, objeto, estado y demás metadatos de origen.

Se lee **todo** el array JSON `var mapa` de cada ficha, sin ejecutar JavaScript.
Sus ramas repiten documentos: se agrupan por URL, conservando todas las claves de
rama en `grupos_fuente`. Cada instrumento sigue siendo un único registro. El
array completo incluye documentos que no se ven al abrir una sola rama del árbol.
Las tablas documentales se paginan en el cliente sobre ese array completo.

El inventario principal sí pagina en servidor: se recorren todas las filas hasta
`iTotalDisplayRecords`, verificando totales, duplicados y páginas vacías. Cambios
de estructura, instrumentos sin documentos o respuestas inconsistentes fallan
antes de sustituir la salida. No existe tope silencioso. `update_proyectos`
refresca el inventario completo, sin cursor temporal.

Los enlaces de descarga requieren abrir primero la ficha del instrumento **en
la misma sesión HTTP**. Una descarga aislada devuelve una página HTML de error
con HTTP 200. Tras abrir la ficha se verificaron muestras reales PDF de ambos
instrumentos; no se descargó todo el corpus. `document_access` documenta este
requisito. Los prefijos PDF y resultados están en evidence.

## Semántica y límites

Cobertura parcial: no se promete inventario de modificaciones, planeamiento de
desarrollo, obras públicas, expedientes en tramitación ni concesiones. La búsqueda
halló asimismo resoluciones BOJA relativas a modificaciones (por ejemplo
https://www.juntadeandalucia.es/boja/2015/34/19 y
https://www.juntadeandalucia.es/boja/2013/238/11); no se agregan como si formasen
parte de esta vista del inventario ni se duplican documentos de un instrumento.

Las fechas de aprobación se conservan literalmente en `fecha_aprobacion_fuente`
y `metadatos_fuente`, con año de dos cifras. No se infieren siglos, fecha de
acuerdo ni fecha de publicación. La actualización global de SITUA tampoco se usa
como fecha del instrumento. El estado «Vigente» es metadato de la ficha, no una
verificación jurídica independiente. No hay coordenadas ni geocodificación.

El esquema del manifest usa `proyectos.source: ayuntamiento` para la ruta de
adaptador municipal; la fuente efectiva se declara expresamente en las notas y
en los registros (`source: junta_de_andalucia`). Licencias, programación y jitter
están desactivados; `publication_ready: false` en cada registro.

## Validación reproducible

Runtime autorizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_cortegana -v`: seis pruebas correctas. Comprueban
  identidad territorial, documentos agrupados y aislados, rechazo de vacíos y
  fuentes ajenas, fechas sin inferencias, paginación completa y fallos sin
  sobrescribir la salida, además de carga de manifest/adaptador.
- Ejecución real con `load_manifest('cortegana')`, `load_portal_adapter(...)` y
  `backfill_proyectos(Path('evidence/proyectos.jsonl'))`. Se pasó `capture_dir`
  local por configuración para capturar las respuestas vivas.
- `evidence/proyectos.jsonl`: dos registros reales con 64 enlaces agrupados.
  `evidence/validation.json`: recuento, URLs, limitaciones y muestras documentales.
  `inventory-0.json`, `instrument-10606.html`, `instrument-37291.html` conservan
  las respuestas de la ejecución, además de capturas de investigación.

Sin publicación, base de datos, despliegue ni cambios en dependencias o fuentes
compartidas.
