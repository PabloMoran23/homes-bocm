# Corral de Almaguer — INE 45054, Toledo

Investigación y extracción real: 2026-11-09. Comunidad autónoma: Castilla-La Mancha.

## Identificación y descubrimiento

La [ficha oficial de Diputación de Toledo](https://www.diputoledo.es/global/11/50/169/dir-municipios/C/45054) identifica Corral de Almaguer y su web municipal `corraldealmaguer.es`. La portada municipal responde por [HTTP](http://www.corraldealmaguer.es/); HTTPS tanto con www como sin www falla la verificación del nombre del certificado. No se desactiva TLS en el adaptador. La [transparencia de la sede electrónica](https://corraldealmaguer.sedelectronica.es/transparency/) responde y muestra la categoría «URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE», con navegación Wicket dependiente de sesión; no constituye la fuente de este scraper. Se guardaron ambas portadas como evidencia de descubrimiento. No se ha verificado un registro público de licencias concedidas: licencias desactivadas.

## Fuente utilizada y cobertura

[Inventario oficial de acuerdos de expedientes urbanísticos de JCCM, filtrado por título municipal](https://urbanismo.castillalamancha.es/acuerdos-expedientes?title=Corral+de+Almaguer).

Es una fuente autonómica oficial sobre instrumentos del municipio, no un portal municipal de concesiones. El manifest usa el canal existente `proyectos.source: ayuntamiento`; cada registro identifica realmente `source: jccm`, `origen: inventario_acuerdos_urbanismo` y conserva la URL del inventario, fichas y documentos.

El inventario vivo devolvió **10 acuerdos, una página, tres acuerdos seleccionados y dos instrumentos agrupados**:

* **PAU Sector Polígono Industrial de las NNSS de Corral de Almaguer**. Dos certificados asociados a acuerdos de 25/11/2019 y 10/11/2021. El primero figura abreviado como «Sector P.I.» en el listado; la primera página del PDF identifica expresamente el mismo sector Polígono Industrial. Ambos tratan informes favorables sobre la **resolución de la adjudicación**, es decir, su extinción, y no una nueva adjudicación ni ejecución de obras. El registro agrupa los dos acuerdos y conserva los títulos originales y fechas en cada documento.
* **CROTU Modificación Puntual nº 1 POM Corral de Almaguer**. Acuerdo de 05/02/2019. Un certificado enlazado. Se representa el instrumento documentado, sin afirmar aprobación definitiva ni vigencia.

Se excluyeron siete entradas de calificación urbanística o autorización provisional: solar fotovoltaica, interruptor eléctrico, depuradora de bodega, nave agrícola, dos vallados y porche agrícola. No se convierten en licencias municipales concedidas ni en obras públicas. Tampoco se extraen formularios, licitaciones o noticias.

Cobertura **parcial**: el filtro busca el nombre completo en el título del acuerdo. No garantiza todos los instrumentos del municipio (por ejemplo, títulos abreviados o documentos ausentes del inventario), ni incluye el POM completo por inferencia. No es un histórico exhaustivo ni acredita el estado actual de los instrumentos.

## Extracción y semántica

El parser recorre artículos Drupal del inventario, verifica la población exacta y selecciona títulos de instrumentos. Las URLs de fichas y documentos deben pertenecer al dominio oficial y a las rutas esperadas. Los documentos de cada acuerdo se mantienen en su instrumento; el PAU industrial tiene una identidad estable común para los títulos abreviado y completo comprobados.

El contador «Mostrando … de … expediente/s» se contrasta con los artículos y la continuidad entre páginas. Se sigue el enlace siguiente preservando el filtro. Contador ausente, páginas incompletas, ciclos, saltos, cambios de total, documentos ausentes o ausencia de instrumentos utilizables provocan error antes de reemplazar el JSONL. No hay límite que trunque silenciosamente la paginación. La actualización vuelve a leer todo el inventario filtrado; no utiliza una fecha de acuerdo como watermark de publicación.

El filtro temporal del portal dice explícitamente «Fecha del acuerdo». Por ello se escribe `fecha_acuerdo` **en cada documento**, sin atribuir fecha única al PAU con dos acuerdos. No se escriben fechas de publicación o aprobación, coordenadas, fase de ejecución ni licencias inferidas. Se declara `publication_ready: false` y `geometry_status: unavailable`.

## Validación reproducible

Runtime usado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_corral_de_almaguer -v
```

Ocho pruebas correctas: agrupación y fechas, aislamiento documental, exclusiones y población exacta, estructura/documentos ausentes, contador incoherente, rechazo de URL externa, dos páginas e incompletitud sin sobrescribir salida previa, conservación del filtro y resolución por manifest/licencias desactivadas.

Ejecución real mediante `load_manifest`, `load_portal_adapter` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `manifest.portal.config['capture_dir'] = 'evidence'`. El wrapper existente de política de entidades se ejecutó sin modificar código compartido; su clasificación resultó desconocida para ambos instrumentos y se retiene en el JSONL, sin atribuirles un uso inmobiliario inventado.

Evidencias locales, no destinadas a commit:

* `evidence/proyectos.jsonl`: dos instrumentos reales, tres documentos.
* `evidence/validation.json`: `live_records: 2`, diez entradas examinadas, URLs exactas, limitaciones, resultado de pruebas y comprobación de documentos.
* `evidence/inventory-1.html`: captura de la respuesta usada por el adaptador.
* Tres PDF completos: respuesta HTTP 200, tipo `application/pdf`, firma `%PDF-`, tamaño y SHA-256 recogidos en validación. Los PDF de 2019 son escaneados; no se derivaron campos de una extracción de texto vacía. Se guardó además la primera página renderizada del certificado PAU 2019 para comprobar el nombre del sector.

No se han ejecutado publicación, geocodificación, base de datos ni tareas programadas. `schedule.enabled: false`, `geocode.jitter_missing: false`, `licencias.enabled: false`.
