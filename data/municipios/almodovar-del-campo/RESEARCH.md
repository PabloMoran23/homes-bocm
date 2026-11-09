# Almodóvar del Campo — Ciudad Real — INE 13015

Investigación y ejecución real: 2026-11-09. Se revisaron primero el contrato
`municipio/adapters/portal.py`, el cargador de manifests, el registro de
adaptadores y los ejemplos de Chipiona y Manlleu. Sin cambios compartidos.

## Fuentes oficiales y alcance

- https://www.almodovardelcampo.es/ — portada municipal, consultada para descubrir navegación oficial.
- https://www.almodovardelcampo.es/plan-de-ordenacion-municipal/ — inventario documental específico: «Proyecto de POM (Plan de Ordenación Municipal) 2ª Información Pública».
- https://www.almodovardelcampo.es/ciudadanos/ — solicitudes: licencia de obras, prórroga, primera ocupación, etc. Son formularios, no concesiones; excluidos.

La página del POM identifica al Ayuntamiento y explica la segunda exposición del
instrumento y su Informe de Sostenibilidad Ambiental. La tabla completa contiene
diez enlaces: memoria informativa, memoria ISA, planos de información, planos ISA,
memoria justificativa, planos de ordenación, normas urbanísticas, fichas de gestión,
memoria de catálogo y fichas de catálogo. Se agrupan todos en **un instrumento**,
con título y URL de cada documento, conservando la página municipal como
procedencia. Los documentos están alojados en Google Drive pero enlazados por el
Ayuntamiento; no son fuentes descubiertas independientemente ni proyectos distintos.

La extracción comprende toda esa tabla, sin límite de filas. No hay paginación en
la página observada. Si aparece navegación de página siguiente o partes del
contenido, el adaptador falla explícitamente para evitar una extracción truncada.
No se recorre el archivo de noticias ni se convierten anuncios de contratación en
proyectos. La cobertura es parcial: este paquete documental concreto, sin afirmar
que agote las obras o instrumentos del municipio. Tampoco demuestra vigencia actual.

## Fechas, identidad y geometría

El texto indica que el periodo de información pública comienza el 28 de enero de
2022, durante 45 días. Se conserva como `fecha_inicio_informacion_publica`, nunca
como fecha de publicación, acuerdo o aprobación. Estas últimas quedan nulas.
La fecha de la legislación citada y posibles fechas del CMS no se usan. La fase
reproduce la segunda información pública descrita por la página histórica; no
supone que el trámite siga abierto hoy ni que el POM esté aprobado.

Identificador estable derivado de la URL del instrumento, sin inventar un número
de expediente. El contrato común de clasificación deja este registro como
`pendiente / insufficient_identity_evidence`: no hay referencia administrativa
numérica verificada; se conserva esa limitación sin forzar elegibilidad.
Sin coordenadas ni geometría verificadas, `publication_ready=false`.
Licencias, programación y jitter desactivados en el manifest.

## Verificación reproducible y evidencia local

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_almodovar_del_campo -v`: **5 correctas**.
Verifican agrupación y procedencia, fechas sin inferencias, exclusión de formularios,
cambios del instrumento, tabla incompleta, duplicados, paginación y licencias
sin acceso de red. Son fixtures sintéticos independientes de los archivos locales.

Ejecución real mediante `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **1 registro, 10 documentos**.
Se aplicó también la anotación común del registro de adaptadores. No se invocaron
bases de datos, geocodificación ni publicación. `update_proyectos` refresca el
paquete completo; no usa fechas de CMS como cursor incremental.

Evidencia local no destinada a commit:

- `evidence/proyectos.jsonl`: resultado real.
- `evidence/validation.json`: recuento, URLs, hash de la captura, pruebas y límites.
- `evidence/pom.html`, `home.html`, `solicitudes.html`: capturas HTTP oficiales.
- `evidence/document_checks.json`: comprobación de los diez enlaces con GET en
  streaming, leyendo solo los primeros 1024 bytes. Todos devolvieron HTTP 200;
  siete tenían firma `%PDF`, tres devolvieron HTML. No se considera HTTP 200 prueba
  suficiente de acceso al PDF. No se descargaron completos los documentos ni se
  verificaron sus contenidos jurídicos o técnicos. Se conservan todos los enlaces,
  incluidos los tres con respuesta HTML; no se eludieron pantallas de confirmación.
- `evidence/proyectos.entities.json`: informe de clasificación común.
