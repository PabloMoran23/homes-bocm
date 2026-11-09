# Nava — Asturias — INE 33040

Investigación y extracción en vivo: 2026-11-09. Un único adaptador municipal,
`municipio.adapters.nava:NavaAyuntamientoAdapter`. Cobertura parcial deliberada:
inventario de documentos de planeamiento publicado por el Ayuntamiento, sin
histórico integral de expedientes, proyectos de obras o licencias concedidas.

## Fuentes oficiales descubiertas y comprobadas

- https://www.ayto-nava.es/urbanismo-y-vivienda — HTTP 200, inventario HTML
  municipal de Urbanismo. Incluye cinco secciones con documentación concreta,
  no meras descripciones de trámites. Es la fuente del adaptador.
- https://www54.asturias.es/rpgur/action/publico/welcome — HTTP 200. Registro
  regional enlazado por la página municipal, con interfaz de consulta. El propio
  Ayuntamiento indica que contiene planeamiento general vigente, modificaciones
  y buena parte de los instrumentos aprobados definitivamente por la CUOTA.
  No se ha recorrido esa consulta ni se presume cobertura de su contenido.
- https://www.ayto-nava.es/catalogo-oficina-tecnica — HTTP 200, catálogo de
  procedimientos. Las entradas de concesión de licencias, planes o proyectos
  describen procedimientos; no son actos concedidos ni proyectos individualizados.
- https://aytonava.sedelectronica.e-ayuntamiento.es/catalogoservicios.aspx —
  HTTP 200, catálogo de servicios de la sede municipal. Incluye un trámite de
  alegaciones a la revisión parcial / Plan Especial de Aguas de Fuensanta.
  No se convierte el formulario en otro instrumento o en una licencia.

Los cuerpos de estas cuatro respuestas se conservan en `evidence/`. No se ha
investigado con credenciales ni se ha tratado el catálogo como registro de actos.
No se utiliza contratación ni noticias para producir registros.

## Registros y agrupación

Se extraen **5 registros y 27 enlaces**. La agrupación sigue los encabezados del
inventario municipal; cada documento conserva título, URL, sección y URL de la
página que lo publica. Los anexos, fichas y planos no generan proyectos adicionales.

| Sección municipal | Documentos | Alcance |
| --- | ---: | --- |
| Normas Subsidiarias | 8 | Normativa, catálogo, fichas y planos |
| Revisión parcial de las normas subsidiarias | 7 | Evaluación ambiental, gráfica, memoria y anexos del ámbito de Fuensanta |
| Normativa Parque Empresarial de la Sidra | 1 | Normativa publicada del Plan Especial |
| Plan Especial de Ceceda | 9 | Normativa, siete grupos de fichas de edificios y planos |
| PERMEUN | 2 | Documento del plan y planos |

Se descargó por separado el primer PDF de cada grupo: HTTP 200 y firma `%PDF`
en los cinco casos, conservados como `evidence/instrumento-1.pdf` hasta
`instrumento-5.pdf` en el orden anterior. Los enlaces exactos permanecen en
`proyectos.jsonl` y `validation.json`; el adaptador conserva incluso los parámetros
de descarga. Estos controles no equivalen a comprobar todos los 27 cuerpos.

La lectura con `pdftotext` aporta contexto importante sobre procedencia:

- El documento ambiental de la revisión identifica el ámbito de Aguas de
  Fuensanta, Buyeres, Nava. La fecha de redacción y la de firma de una copia no
  son fechas de aprobación del instrumento.
- El PDF de Sidra, cuyo rótulo municipal habla de aprobación definitiva del Plan
  Especial, contiene el acuerdo de **27 de mayo de 2009 sobre una modificación
  puntual**, publicado en el BOPA de **15 de junio de 2009**. No es evidencia de
  la aprobación original del Plan. El registro conserva la agrupación municipal
  como normativa publicada y deja la fase y las fechas sin determinar.
- El PDF PERMEUN incluye el **boletín completo de 9 de enero de 1999**, con
  contenido del Plan Especial de recuperación y mejora del entorno urbano de
  Nava, además de disposiciones ajenas. Se conserva como documento vinculado al
  instrumento; no se extraen proyectos de las otras disposiciones del boletín.
- El PDF de Ceceda no devuelve texto en sus dos primeras páginas mediante
  `pdftotext`; no se aplica OCR ni se deducen fechas de ese archivo.

El adaptador extrae el inventario HTML, no texto de PDF. No introduce como
constantes fechas o números de expediente leídos manualmente. `fecha`,
`fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` y `fase` permanecen nulos.
Los parámetros `t=` son marcas técnicas del repositorio y no fechas legales.
El nombre del grupo tampoco acredita que todos sus documentos compartan fase.

## Comportamiento y límites

Una petición HTTPS al inventario, con tiempo límite y máximo de 3 MB; los
excesos provocan error, nunca truncado aceptado. El HTML examinado es una página
sin paginación. Se comprueba la ausencia de indicadores de paginación y se
exigen las cinco secciones revisadas, sin duplicados. Una sección nueva,
desaparecida, sin documentos, un cambio de estructura o una URL documental ajena
al repositorio municipal provoca error para revisión. No hay corte por número
de registros ni recorrido de páginas limitado silenciosamente.

Los identificadores son estables por instrumento municipal y no dependen del
orden de los PDF o de sus marcas de carga. Las actualizaciones refrescan la
instantánea completa, incluidas desapariciones; `state_path` no se usa como
cursor de fechas. La salida solo se sustituye tras completar el parseo.

No se afirma haber encontrado todas las modificaciones de cada instrumento,
actos de aprobación, obras físicas ni expedientes de Nava. El propio inventario
remite a RPGUR para una consulta más amplia. No hay coordenadas ni geometrías
extraídas de los planos; no se sustituye con centroides municipales ni ubicaciones
aleatorias. `publication_ready` es falso. El manifest desactiva programación,
jitter y licencias. Los métodos de licencias generan salida vacía y estado
desactivado.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `python -m unittest municipio.test_nava -v`: **8 pruebas correctas**. Verifican
  agrupación de anexos anidados, procedencia, fechas y geometrías ausentes,
  rechazo de login/navegación, secciones alteradas, paginación, documentos ausentes
  o ajenos, duplicados, carga del manifest, licencias y reemplazo de instantánea.
- Extracción real mediante `load_manifest('nava')`, `load_portal_adapter(manifest)`
  y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **5 registros,
  27 enlaces**, estado `ok`. Se usó `capture_dir=evidence` como configuración local
  para conservar el mismo HTML consumido por el adaptador.
- El envoltorio compartido de política de entidades informó `total=5`,
  `unknown=5`, `status=ok`. No se forzó una categoría ni elegibilidad para publicar.
- `evidence/validation.json` contiene el recuento real, URLs, resultado del
  adaptador y limitaciones. La evidencia es local y no forma parte de los cuatro
  archivos fuente entregados.
