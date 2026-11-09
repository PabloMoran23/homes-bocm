# Las Pedroñeras — Cuenca — INE 16154

Investigación y extracción comprobadas el 9 de noviembre de 2026.

## Descubrimiento de fuentes oficiales

La página municipal https://laspedroneras.es/ enlaza la sede oficial
https://laspedroneras.sedelectronica.es/ y la Oficina Técnica:
https://laspedroneras.es/index.php?option=com_k2&view=itemlist&layout=category&task=category&id=16&Itemid=419 .
Esta última muestra datos del departamento, sin inventario utilizable de proyectos.
Se guardan ambas páginas en `evidence/home.html` y `evidence/oficina-tecnica.html`.

El portal de transparencia https://laspedroneras.sedelectronica.es/transparency
permite abrir la carpeta «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE»:
https://laspedroneras.sedelectronica.es/transparency/b4db9227-73d6-4b3a-9047-e7c30047e513/ .
La carpeta anuncia 206 documentos: 205 son análisis de agua y uno pertenece a
planes/programas medioambientales. Las carpetas de planeamiento urbanístico,
normativa urbanística y obras públicas tienen cero documentos. No se interpreta
el contador global como número de proyectos. Capturas: `evidence/transparency.html`
y `evidence/urbanismo.html`. Los trámites de solicitud de licencia de la sede no
constituyen concesiones; licencias queda desactivado. No se utilizan anuncios de
contratación, noticias, ni actas provinciales generales como proyectos sintéticos.

## Fuente implementada y cobertura

Inventario oficial de la Junta de Comunidades de Castilla-La Mancha:
https://urbanismo.castillalamancha.es/registros/pau-cu .
El registro provincial contiene siete entradas en una página, sin enlaces de
paginación en la extracción observada. La selección exige el texto exacto
«Pedroñeras, Las» en la columna municipal. La ficha debe confirmar simultáneamente
«CUENCA», «Pedroñeras, Las» y el mismo título que el inventario.

Resultado vivo: **un programa urbanizador real**, PAU UA-Norte del Sector 1
«Hoya del Moro», con ficha individual:
https://urbanismo.castillalamancha.es/registros/pau/pau-ua-norte-del-sector-1-hoya-del-moro .
El agente urbanizador publicado es REGAR AGRÍCOLA S.L.; el uso es industrial.
El identificador se deriva de la URL de ficha y no de su posición en el listado.

Se recorren todos los enlaces del paginador Drupal (numerados, siguiente y último),
con deduplicación y comprobación de host/ruta; no hay límite de registros ni corte
por fecha. Las actualizaciones repiten el inventario completo. Un cambio de
estructura, una ficha incompatible o la desaparición de todas las entradas del
municipio genera error antes de sustituir el resultado anterior.

La cobertura es **parcial**: PAU inscritos en el registro autonómico provincial,
no todas las modificaciones de planeamiento, obras ni expedientes del ayuntamiento.
La fuente se identifica por registro como `source: jccm` y
`origen: registro_autonomico_pau_cuenca`. El manifest usa el canal `ayuntamiento`
del contrato de proyectos para ejecutar el adaptador portal; sus notas explicitan
que la procedencia efectiva es autonómica. La existencia de una ficha no acredita
vigencia actual, comienzo de obras o concesión de una licencia.

## Fechas, documentos y geometría

La cabecera del listado provincial dice «Fecha de constitución», aunque la celda
usa la clase interna `field-fecha-aprobacion`. El adaptador **no toma esa celda**.
Obtiene `fecha_aprob: 2019-04-01` exclusivamente del campo explícito «Fecha de
aprobación» de la ficha. La inscripción del 5 de agosto de 2019, número 001/2019,
se conserva literalmente en `datos_inscripcion`; no se convierte en fecha de
aprobación ni en referencia de expediente municipal. No se deducen fechas de
publicación o acuerdo, ni fases a partir del tipo.

La ficha observada no tiene documentos adjuntos: `documentos: []` refleja esa
limitación. La URL de ficha es la procedencia verificable. Si aparecen adjuntos
oficiales bajo `/sites/default/files/` dentro del artículo, se agrupan en el mismo
PAU, con título, URL y página de origen, sin generar un proyecto por archivo.
No se incluyen documentos de menús o pies de página.

No se inventan coordenadas ni polígonos; `geometry_status: unavailable` y
`publication_ready: false`. `schedule.enabled`, `geocode.jitter_missing` y
`licencias.enabled` son falsos. La política compartida de entidades clasifica la
salida como `pendiente / insufficient_identity_evidence`, con
`activity_eligible: false`, porque no hay referencia de expediente municipal; se
conserva esta clasificación y no se fuerza su elegibilidad.

## Validación reproducible

Runtime usado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_las_pedroneras -v
```

Diez pruebas correctas: filtro municipal exacto, rechazo de cambios de estructura,
semántica de fechas, ausencia de aprobación no inferida, identidad provincial de
fichas, agrupación/aislamiento de adjuntos, paginación, recorrido completo con
ciclos y actualización idempotente, fallo atómico e inventario municipal vacío,
manifest y licencias desactivadas.

La ejecución real carga `load_manifest('las-pedroneras')`, configura
`manifest.portal.config['capture_dir'] = 'evidence/live-captures'`, resuelve
`load_portal_adapter(manifest)` y llama a
`adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
Se verificaron INE y provincia en todos los registros resultantes. Evidencias
locales: `evidence/proyectos.jsonl`, `evidence/validation.json` con `live_records: 1`,
URLs, limitaciones y resultado de la política compartida; las dos respuestas HTML
de esa ejecución están en `evidence/live-captures/`, identificadas por hash de URL.
Las capturas de descubrimiento también permanecen bajo `evidence/`.
No se instala software ni se ejecutan publicación, geocodificación o acceso a bases de datos.
