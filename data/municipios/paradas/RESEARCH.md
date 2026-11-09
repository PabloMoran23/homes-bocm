# Paradas (Sevilla), INE 41071

Investigación y extracción en vivo: 9 de noviembre de 2026. Adaptador único:
`municipio.adapters.paradas:ParadasAyuntamientoAdapter`.

## Descubrimiento oficial y alcance

La [portada del portal de transparencia municipal](https://transparencia.paradas.es/es/)
enlaza directamente el indicador [PLANEAMIENTO Y GESTIÓN](https://transparencia.paradas.es/es/transparencia/indicadores-de-transparencia/indicador/PLANEAMIENTO-Y-GESTION./).
Esta es la fuente de extracción. Es un inventario documental servido actualmente
como un artículo OpenCMS completo, con 16 bloques de instrumentos y sin controles
de paginación observados. El parser procesa todos sus bloques; ante controles de
paginación detectados falla explícitamente y exige revisar la navegación.

También se consultaron:

- [Delegación de Urbanismo y Medio Ambiente](https://www.paradas.es/es/ayuntamiento/delegaciones/detalle/Urbanismo-y-Medio-Ambiente-00002/): competencias y noticias; no se convierten en proyectos ni licencias.
- [Convenios urbanísticos y actuaciones](https://transparencia.paradas.es/es/transparencia/indicadores-de-transparencia/indicador/Convenios-urbanisticos-del-Ayuntamiento-y-de-las-actuaciones-urbanisticas-en-ejecucion.-Plan-de-Emergencia-Municipal./): inventario separado que mezcla suspensión de tramitación, convenios, correcciones de NNSS y plan de emergencia. No lo procesa este adaptador. La suspensión relacionada con la implantación en suelo no urbanizable impide interpretar el simple inventario de planeamiento como certificación de vigencia.

Se guardaron capturas HTML de las cuatro páginas en `evidence/`. No se ha
verificado un registro público de licencias concedidas. No se usan formularios,
anuncios de contratación ni noticias como sustitutos de expedientes.

## Resultado y agrupación

La extracción real mediante `load_manifest('paradas')`, `load_portal_adapter()` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))` devuelve **15 registros** y
**70 URLs documentales distintas**. La política de entidades del cargador informa
15 entidades reconocidas, cero desconocidas. La extracción consume la web en vivo;
no contiene registros ni títulos de instrumentos precargados.

Los instrumentos incluyen el avance del PBOM con su DIE y memorias/cartografía,
el estudio de detalle Pío XII, modificaciones del PGOU (dotaciones, suelo no
urbanizable, Los Arenales, antigua sede de Correos y artículos 5.2.0.2/5.2.0.3),
las modificaciones diferenciadas del plan parcial Los Alberos, los estudios de
detalle Rafael Alberti y Manuel Jesús «El Cid», dos PERI y la modificación de
altura de edificios de las NNSS.

Cada bloque aporta un instrumento con sus memorias, planos, acuerdos y anuncios,
conservando títulos, secciones y URLs. Los dos bloques de la modificación número
3 de Los Alberos se agrupan por título normalizado (acentos y puntuación),
reteniendo ambos títulos originales. Los números de modificación no se eliminan:
la modificación 2 y la modificación sin número permanecen separadas. Documentos
repetidos con distintas etiquetas se conservan como asociaciones de procedencia.
La URL principal es el primer PDF del instrumento; `inventory_url` identifica el
inventario y cada documento conserva `source_url`.

El propio portal enlaza algunos PDF bajo varios instrumentos: por ejemplo,
`Anuncio-Bop-aprobacion-definitiva.pdf` aparece bajo dotaciones, Correos y la
modificación del plan parcial. El scraper retiene lo publicado, sin concluir que
los instrumentos sean iguales ni que el PDF apruebe todos ellos. No se deduplican
instrumentos por compartir un enlace.

## Fechas, geometría y límites

Los rótulos «aprobación inicial/definitiva» se guardan como texto de procedencia;
no son una fase o aprobación verificada. Las fechas del CMS (por ejemplo, 9 de
junio de 2023 en documentos de suelo no urbanizable), las fechas incrustadas en
nombres de archivo y las fechas de un acuerdo son conceptos diferentes. El
adaptador no extrae fechas normalizadas de ninguno de esos lugares ni deduce
fecha de aprobación o publicación. Tampoco comprueba el contenido y la vigencia
de cada PDF. No inventa coordenadas: `geometry_status: unavailable` y
`publication_ready: false` en todos los registros.

Cobertura parcial del inventario seleccionado, sin garantizar exhaustividad
municipal, historia de expedientes, otras fuentes de planeamiento ni obras en
ejecución. El inventario de convenios y sus documentos adicionales quedan fuera.
No se geocodifica, programa ni publica: `schedule.enabled=false`,
`geocode.jitter_missing=false`, `licencias.enabled=false`.

## Validación reproducible

Runtime preinstalado utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Tests ejecutados:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_paradas -v
```

Cinco tests correctos: agrupación y separación de instrumentos, exclusión de
formularios/noticias/licitaciones, ausencia de metadatos inventados, errores ante
paginación/estructura vacía/documentos ajenos, escritura del snapshot sin
sobrescribir ante error y controles del manifest. Los tests son independientes
de las capturas locales.

La ejecución real guardó `evidence/proyectos.jsonl` y `evidence/validation.json`,
con contador, fuentes, limitaciones, resultado del cargador y comprobaciones de
PDF. Se compararon además los IDs del resultado con una segunda descarga del
inventario, guardada como `evidence/planeamiento.html`.

Dos descargas de muestra verificadas, HTTP 200, `application/pdf` y firma `%PDF-`:

- [Acuerdo del estudio de detalle Pío XII](https://transparencia.paradas.es/export/sites/paradas/es/transparencia/.galleries/IND-53-/Cdo_Pleno_2024_11_19_P3_Aprobacion_Definitiva_Estudio_de_...-Firmad.pdf): 165773 bytes, captura `evidence/pio-xii-acuerdo.pdf`.
- [Memoria sobre implantación en suelo no urbanizable](https://transparencia.paradas.es/export/sites/paradas/es/transparencia/.galleries/IND-53-/PPI_DA_MEMORIA.PDF): 685591 bytes, captura `evidence/suelo-no-urbanizable-memoria.pdf`.

Esta comprobación de disponibilidad y formato no certifica los otros PDF ni el
contenido jurídico. La evidencia es local; no forma parte de los cuatro archivos
fuente entregados. No se ejecutaron bases de datos, despliegues ni publicación.
