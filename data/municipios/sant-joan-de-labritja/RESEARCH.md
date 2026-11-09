# Sant Joan de Labritja — INE 07050, Illes Balears

Revisión y extracción real: 2026-11-09. Cobertura deliberadamente parcial del
inventario municipal de Normas Subsidiarias (NNSS). No es un censo de obras,
licencias concedidas ni de todo el planeamiento del municipio. La presencia en
esta página no certifica por sí sola la vigencia jurídica actual de cada documento.

## Fuentes oficiales descubiertas

- Área municipal de Obras y Urbanismo:
  https://www.santjoandelabritja.com/index.php/es/area-obras-y-urbanismo
  (HTTP 200). Su navegación utiliza Smart Slider y enlaces `data-href`.
- Inventario NNSS utilizado:
  https://www.santjoandelabritja.com/index.php/es/nnss (HTTP 200).
  Contiene memoria, BOIB, planos por núcleos, cartografía TIF, anexos de patrimonio
  y modificaciones 5 y 7. Página única sin controles de paginación observados.
  Se leen tanto `href` como `data-href`: utilizar sólo las etiquetas `a` perdería
  planos y la modificación 7.
- https://transparencia.santjoandelabritja.com/ (HTTP 200): el HTML recibido es
  una aplicación Next.js, sin inventario de proyectos en el contenido estático;
  `__NEXT_DATA__` sólo contiene traducciones, no registros. No se extraen proyectos
  ni se afirma cobertura de este portal dinámico.
- Los resultados oficiales de búsqueda también muestran
  https://www.santjoandelabritja.com/index.php/es/tramites-obras-y-urbanismo y
  https://www.santjoandelabritja.com/index.php/es/urbanismo-y-vivienda-2/solicitud-de-aprobacion-de-planeamiento-de-desarrollo.
  Son trámites/formularios, excluidos; no acreditan concesiones ni instrumentos
  individuales. No se ha verificado un registro público de licencias concedidas.

## Instrumentos y procedencia documental

Los tres actos se descargaron desde los espejos documentales del Ayuntamiento,
con respuesta HTTP 200 y contenido PDF. El emisor del acto es la CIOTUPHA del
Consell Insular d'Eivissa; la publicación es BOIB. No se confunde la fecha de
carga o actualización de la web con una fecha del instrumento.

| Instrumento | Expediente del acto | Acuerdo / aprobación definitiva | Publicación BOIB |
| --- | --- | --- | --- |
| Revisión de NNSS | PL-01/2010 | 2011-04-29 | 2011-07-07, núm. 104 |
| Modificación puntual 5 | 2020/10915Y | 2021-04-12 | 2021-04-24, núm. 54 |
| Modificación puntual 7 | 2021/15083F | 2022-07-06 | 2022-07-09, núm. 89 |

- NNSS: https://www.santjoandelabritja.com/documentos/NNSS/NNSS_BOIB.pdf.
  El título identifica la revisión del planeamiento general mediante NNSS.
  Este PDF incluye en su primera página noticias de otros municipios: no se
  convierten en registros. Tampoco se usa la aprobación provisional de 2007 como
  aprobación definitiva.
- Modificación 5:
  https://santjoandelabritja.com/documentos/NNSS/modificacion_puntual_boib/BOIB_aprobacion_mod5.pdf.
  Regula actividades complementarias al alojamiento turístico y actividades
  musicales de ocio/entretenimiento. Aprobación definitiva con prescripciones.
  El documento imprime como referencia BOIB
  https://www.caib.es/eboibfront/pdf/es/2021/54/1086249 (no se requiere otra descarga).
- Modificación 7:
  https://www.santjoandelabritja.com/documentos/PTI/MODIFICACI%C3%93N%20N%C2%BA%207%20PARCELA%20CA-1%20Y%20EL-PR%20EN%20S.JOAN.pdf.
  Ordenación de una parcela CA-1 y ELPR en el núcleo de Sant Joan. El PDF imprime
  https://www.caib.es/eboibfront/pdf/ca/2022/89/1115218 (referencia, no otra fuente
  descargada). Aunque el archivo está bajo `/PTI/`, es una modificación de las
  NNSS municipales, no un registro del plan territorial insular completo.

## Extracción y límites

Se emiten tres registros de instrumento, con 31 documentos enlazados en total:
29 para NNSS, uno para la modificación 5 y uno para la 7. Los planos de núcleos,
la memoria, el anexo VI y el catálogo patrimonial se agrupan con las NNSS;
los duplicados para escritorio/móvil se eliminan por URL, preservando títulos.
Las ordenanzas de protección y la instrucción técnica de patrimonio son reglas
independientes, no proyectos; se excluyen. El PTI enlazado por navegación queda
fuera de este alcance municipal.

Sólo los tres PDF BOIB se descargan y verifican en cada ejecución. Los otros
28 adjuntos se conservan como enlaces del inventario, marcados
`linked_not_fetched`: su disponibilidad y contenido no están verificados.
Cada acto descargado conserva SHA-256 y URL. Las fechas se extraen del encabezado
del acuerdo y la cabecera BOIB, con soporte español/catalán; `fecha` queda null.
Las afirmaciones de aprobación reflejan esos actos históricos, sin certificar
que no existan modificaciones posteriores o recursos.

Se usa `pdftotext` ya disponible en `/usr/bin/pdftotext`, sin instalación ni cambios
de dependencias. Su modo de lectura predeterminado preserva las columnas del
BOIB antiguo: el modo `-layout` intercala texto de la otra columna. Se rechazan
contenido vacío, expedientes incompatibles, fechas ausentes, PDF falsos,
redirecciones fuera del dominio y nueva paginación; no se devuelve un éxito vacío.
Las respuestas están acotadas a 5 MB HTML y 10 MB por acto, con timeout y escritura
atómica al completar el snapshot. Update vuelve a leer el inventario entero.
No se hace recorte por número de registros.

Sin coordenadas o geometrías verificadas: `lat`, `lon` y `geometry` null,
`publication_ready=false`. No se sustituyen por centroides ni se geocodifica por
aproximación. `schedule.enabled=false`, `geocode.jitter_missing=false` y
`licencias.enabled=false`.

## Validación reproducible

Runtime solicitado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `python -m unittest municipio.test_sant_joan_de_labritja -v`: ocho tests offline
  verifican agrupación y deduplicación, enlaces Smart Slider, exclusión de
  formularios/reglas, paginación, dominios, fechas y referencias en ambos idiomas,
  errores sin sustituir un snapshot y configuración del manifest.
- Extracción real con `load_manifest`, `load_portal_adapter` y
  `backfill_proyectos(Path('evidence/proyectos.jsonl'))`; `capture_dir=evidence`
  sólo se añade a la configuración en memoria para guardar capturas locales.
- Evidencia local sin commit: `evidence/proyectos.jsonl`,
  `evidence/validation.json`, `evidence/nnss-inventory.html`, los tres actos en
  PDF/texto y capturas de descubrimiento. El informe incluye cantidad real,
  fuentes y limitaciones. El envoltorio normal del registro aplica entity_policy.
