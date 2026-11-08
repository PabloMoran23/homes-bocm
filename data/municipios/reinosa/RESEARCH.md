# Reinosa — Cantabria — INE 39059

Investigación y extracción real: 8 de noviembre de 2026. Único adaptador añadido: `municipio.adapters.reinosa:ReinosaAyuntamientoAdapter`.

## Fuente oficial y selección

Inventario consultado en vivo: https://www.aytoreinosa.es/normativa/#Planifica (petición HTTP a https://www.aytoreinosa.es/normativa/).
La página municipal separa Ordenanzas, Reglamentos y PGOU. Dentro de `#Planifica`, las categorías BSK PDF Manager `cat-6`, `cat-7` y `cat-8` contienen respectivamente Documentos PGOU, Modificaciones Puntuales y Planes Parciales. El adaptador lee únicamente estas categorías y conserva los títulos y enlaces PDF oficiales. No extrae ordenanzas generales, formularios de licencia, anuncios de contratación ni noticias.

Resultado observado: **16 registros y 37 documentos enlazados**:

- Un registro del Plan General, con los 22 documentos que el Ayuntamiento agrupa en Documentos PGOU: memoria, normas, fichas, catálogo, estudio económico, planos y revisión del programa de actuación. No se convierten las hojas cartográficas en proyectos separados.
- Catorce entradas de modificaciones: 01, 02 a 08, 09, 10, 12, 13, 14, 15, 17, 18, 19, 20, 21 y 23 a 29. Los dos paquetes colectivos se conservan como agrupaciones documentales originales, sin crear registros individuales a partir de los extremos de un intervalo ni inventar las modificaciones ausentes.
- Una modificación de las ordenanzas del Plan Parcial del Polígono Industrial La Vega. Se incluye por ser una modificación de un instrumento urbanístico concreto, diferenciada de las ordenanzas municipales generales.

Ejemplos documentales oficiales comprobados:

- Normas del PGOU: https://www.aytoreinosa.es/wp-content/uploads/bsk-pdf-manager/NORMAS_URBANISTICAS_35.pdf
- Modificación 01: https://www.aytoreinosa.es/wp-content/uploads/bsk-pdf-manager/MODIFICACION_PUNTUAL_1_53.pdf
- Paquete 23 a 29: https://www.aytoreinosa.es/wp-content/uploads/bsk-pdf-manager/MODIFICACIONES_PUNTUALES_23_a_29_66.pdf
- La Vega: https://www.aytoreinosa.es/wp-content/uploads/bsk-pdf-manager/20021227_-_MODIFICACION_ORDENANZAS_DEL_PLAN_PARCIAL_POLIGONO_INDUSTRIAL_LA_VEGA_889.pdf

La búsqueda también localizó una noticia municipal sobre la actualización del PGOU (https://www.aytoreinosa.es/ayuntamiento-reinosa-retoma-la-actualizacion-del-pgou-tras-cuatro-anos-paralizado/) y documentos de revisión en `/wp-content/uploads/2017/10/`. No se incorporan a este inventario: no se ha verificado aquí un índice documental completo de esa revisión ni su relación jurídica con cada documento de Normativa.

## Cobertura y semántica

Cobertura parcial: el inventario documental actualmente accesible en Normativa, no un registro completo de planeamiento, obras públicas, acuerdos o licencias del municipio. No se afirma que los instrumentos estén vigentes, aprobados o ejecutados. No se interpreta el contenido de los PDF ni se deduce su ámbito geométrico.

No se emiten `fecha`, `fecha_publicacion`, `fecha_acuerdo` ni `fecha_aprob`: el inventario no proporciona fechas con esas funciones verificadas. Una fecha en el nombre de archivo, ruta de subida o metadato del CMS no se transforma en fecha de aprobación o publicación. Se conserva el enlace original, incluido el nombre del archivo. `source_url` de cada documento y `inventory_url` identifican su procedencia; `checked_at` en la evidencia es la fecha de comprobación, no un acuerdo municipal.

No hay coordenadas ni fases inferidas. Todos los registros llevan `publication_ready: false` y `geometry_status: unavailable`. Licencias, programación y jitter geográfico están desactivados en el manifiesto.

Las tres listas estaban renderizadas completas en una única página; no se observó paginación ni carga adicional. El parser rechaza indicadores de paginación/carga adicional, categorías ausentes o nuevas, listas vacías, títulos de modificación desconocidos y enlaces documentales ajenos al dominio oficial. Un cambio de estructura requiere revisión, no produce silenciosamente una primera página parcial. `update_proyectos` vuelve a leer el inventario completo porque no existe un cursor temporal fiable. La escritura es atómica tras validar el listado.

## Validación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_reinosa -v`, **7 correctas**. Verifican agrupación de documentos, deduplicación, retención de paquetes colectivos, aislamiento de documentos entre instrumentos, exclusión de formularios externos a PGOU, ausencia de fechas/coordenadas/fases deducidas, rechazo de paginación y cambios de estructura, actualización y conservación del archivo previo ante errores, y manifiesto.

Extracción real ejecutada directamente con `ReinosaAyuntamientoAdapter('reinosa', config={'capture_dir': 'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.

Evidencia local, no destinada a commit:

- `evidence/proyectos.jsonl`: los 16 registros reales.
- `evidence/normativa.html`: captura de la respuesta utilizada por el adaptador.
- `evidence/validation.json`: recuentos, URLs, limitaciones, fecha de comprobación, hash de la captura y comprobaciones documentales.
- `evidence/*.pdf.prefix`: primeros 1024 bytes de cada uno de los 37 enlaces documentales, identificados en validation.json. Los 37 respondieron HTTP 200/206 y comenzaron con firma `%PDF-`. Se solicitó un rango y se cerró la respuesta tras el prefijo; no se afirma haber interpretado o validado todos los contenidos del PDF.

No se usaron bases de datos, publicación, despliegue, instalación de dependencias ni geocodificación.
