# Santillana del Mar — INE 39076, Cantabria

Verificado el 9 de noviembre de 2026. Cobertura deliberadamente parcial: un
instrumento, la revisión del PGOU, con sus seis documentos públicos agrupados.
No constituye un inventario municipal completo ni acredita una aprobación
definitiva. `publication_ready: false`; programación, licencias y desplazamiento
aleatorio de coordenadas desactivados.

## Descubrimiento y fuentes oficiales

- [Web municipal](https://santillanadelmar.es/), HTTP 200: la tarjeta «Revisión del
  PGOU» enlaza directamente al inventario implementado. Captura local
  `evidence/municipal-home.html`.
- [Revisión del PGOU](https://santillanadelmar.sedelectronica.es/transparency/7d237b45-2517-4279-9e49-8dbe643f3208/),
  HTTP 200, sin autenticación. Sección «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO
  AMBIENTE/7. REVISION PGOU SANTILLANA DEL MAR». Tabla completa sin paginación
  observada: Tomo I (memoria, información y avance), Tomo II (planos), Tomo III
  (documento inicial estratégico), anuncio BOC, bando y consultas. Los seis enlaces
  estables `preview-document` se conservan con su título y procedencia.
- [Planeamiento urbanístico](https://santillanadelmar.sedelectronica.es/transparency/3edc1a4e-612d-4faa-803a-ca9dfed85988/),
  HTTP 200: otro inventario oficial. Contiene carpetas «PGOU de Santillana del Mar
  (1)» y «Modificaciones puntuales del PGOU de Santillana del Mar (16)», mediante
  controles Wicket, y un documento de estudio de detalle UA SS5A1 Castío. Esos
  números corresponden al índice visible, no a registros extraídos. No se han
  recorrido las carpetas ni incorporado estos instrumentos; quedan fuera del
  alcance de este scraper. Captura `evidence/discovery-1.html`.
- [Anuncio BOC CVE-2024-5602](https://boc.cantabria.es/boces/verAnuncioAction.do?idAnuBlob=406892),
  PDF oficial descargado con HTTP 200 en `evidence/avance-boc.pdf`. Corrobora que
  existe un avance concreto, expediente 1075/2024, con tres tomos y exposición
  pública. Publicación: 2024-07-10. Resolución de apertura de información pública:
  2024-07-02. Firma del anuncio: 2024-07-03. No son fechas intercambiables.
  El scraper no analiza el PDF ni incorpora su expediente o resolución como
  constantes; obtiene la fecha de publicación del título explícito del anuncio
  en el inventario y conserva el enlace a su documento como fuente de esa fecha.

## Extracción y semántica

El adaptador solicita el inventario y las seis páginas públicas de previsualización
con una sesión HTTP anónima. Cada respuesta debe ser HTML del dominio oficial y
tener éxito HTTP; se limita a 4 MB y 40 segundos por petición. Verifica el
encabezado del inventario, tabla única, los tres tomos técnicos, anuncio único,
enlaces de documentos del dominio oficial y metadatos públicos con el título
esperado. Un formulario o enlace de navegación no satisface estas condiciones.

Se genera una identidad estable a partir de la URL del inventario del instrumento,
no un registro por PDF. Se conservan todos los documentos de la tabla, sin límite
de filas ni corte silencioso. Si aparecen controles de paginación o carpetas en
esa tabla, se produce un error que exige implementar su recorrido. Actualizar
relee el inventario entero; no emplea una marca temporal incremental. Un fallo
de validación ocurre antes de escribir el resultado.

`fase` indica exclusivamente que la documentación publicada corresponde al
avance. No demuestra que siga abierto el plazo de información pública ni que
sea la fase administrativa actual. `fecha_publicacion` es 2024-07-10 por el título
«PUBLICACIÓN ANUNCIO AVANCE BOC Nº 133 10.07.24». Si desaparece la fecha explícita,
se deja vacía. No se usan las fechas de los nombres `20240520_TOMO…`, la hora de
la sede, ni la fecha de creación de las previsualizaciones (el anuncio muestra
11-jul-2024) como fechas de aprobación o publicación. `fecha`, `fecha_acuerdo` y
`fecha_aprob` permanecen nulas.

No se han extraído vectores o coordenadas de los planos PDF. `lat`, `lon` y
`geometry` permanecen nulos; no se sustituye geometría por el centro municipal.
No se extraen noticias generales, anuncios de contratación, solicitudes de
licencia ni registros de licencias concedidas. No se ha acreditado un registro
público de estas últimas, por lo que su método devuelve cero y estado desactivado.

## Validación reproducible y evidencia local

Runtime autorizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `python -m unittest municipio.test_santillana_del_mar -v`: seis pruebas pasadas.
  Cubren agrupación, fechas separadas, ausencia de fecha, rechazo de contenido
  incompleto/login, paginación/carpetas/enlaces externos, actualización sin
  duplicación, conservación del resultado ante un fallo y configuración segura.
- Extracción real mediante `SantillanaDelMarAyuntamientoAdapter.backfill_proyectos`
  con `config.evidence_dir` apuntando a `evidence/`: **1 registro, 6 documentos**;
  las siete peticiones de extracción verificaron contenido público válido.
- `evidence/proyectos.jsonl`: resultado real. `evidence/validation.json`:
  `live_records`, URLs consultadas y limitaciones. `revision-inventory.html` y
  seis capturas con UUID de documento: respuestas utilizadas por el adaptador.
  `discovery-sources.json` relaciona las capturas adicionales con sus URLs.

La evidencia es local y no forma parte de los cuatro archivos fuente entregados.
No se han modificado fuentes compartidas, dependencias ni configuración de Git;
no se han utilizado servicios de publicación ni bases de datos.
