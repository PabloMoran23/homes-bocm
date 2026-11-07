# Campos — INE 07013, Illes Balears

Verificación en vivo: 7 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y fuente seleccionada

- [Área municipal de Urbanisme i Activitats](https://ajcampos.net/ca/arees/urbanisme-i-activitats): página institucional de Campos. Describe competencias y enlaza la sede electrónica. No constituye un registro de licencias concedidas. Sus noticias y formularios no se convierten en proyectos.
- [Inicio de la sede](https://ajcampos.sedelectronica.es/info.0): contiene el enlace «Planejament Urbanístic» a la página seleccionada. Las solicitudes de licencia son trámites, no concesiones.
- [Inventario municipal de planeamiento](https://ajcampos.sedelectronica.es/citizen-service/e897c0dd-6e2d-4dc6-ae80-a06d6de5e2a9): declara «Normes Subsidiàries de Planejament de Campos» y normativa actualizada a noviembre de 2025. Ofrece Documentació escrita, Documentación gráfica y Cronologia informativa mediante un árbol Wicket público, sin autenticación.

La fuente efectiva del adaptador es la sección **Cronologia informativa**, titulada «RELACIÓ D’INSTRUMENTS DE PLANEJAMENT APROVATS». Es un inventario oficial de instrumentos concretos, no una noticia de contratación. La fecha de actualización declarada no demuestra exhaustividad posterior ni es una fecha de aprobación/publicación de cada instrumento.

La comprobación exploratoria de Documentació escrita identifica texto refundido, anexos y publicaciones de modificaciones. La sección gráfica abre categorías Sòl Urbà, Sòl Rústic y Altres. El adaptador cubre solamente la cronología, no promete descargar el archivo gráfico ni todos los expedientes municipales. Los XML exploratorios están en `evidence/folder-*.xml`.

## Cobertura y exclusiones explícitas

La cronología tiene ocho entradas numeradas consecutivas. La extracción en vivo produce **seis registros**, correspondientes a:

| Entrada | Instrumento | Fechas de acuerdo narradas | Publicaciones narradas |
| --- | --- | --- | --- |
| 1 | Normes Subsidiàries | 1991-03-26; cumplimiento de prescripciones 1991-06-07 | 1994-05-14 |
| 2 | Modificación puntual | 1993-05-27 | 1993-07-08 |
| 5 | Modificación puntual | 2010-04-23; 2010-05-28 | 2010-05-06; 2010-06-17 |
| 6 | Conformidad con el texto refundido | 2014-01-31 | 2014-02-06 |
| 7 | Modificación: equipamiento de Ses Sitjoles | 2020-07-31 | 2020-08-04 |
| 8 | Modificación puntual | 2024-12-19 | 2024-12-28 |

La entrada 3 se excluye porque la propia fuente declara anulada la modificación por sentencias judiciales. La entrada 4 se excluye porque reúne varias modificaciones de SAU Son Durí y una corrección material sin identidades individuales suficientes para separarlas con rigor. No se inventan expedientes ni se convierte cada fecha o párrafo en otro proyecto.

## Semántica y procedencia documental

Cada entrada admitida conserva su descripción completa, ordinal (`source_item`), sección, URL estable y un documento HTML de procedencia municipal. Las eventuales URLs de documentos insertadas en cada entrada se conservan y deduplican dentro de ese instrumento. Actualmente la cronología **no ofrece enlaces directos a los boletines/PDF**: las referencias BOIB/BOCAIB son afirmaciones del relato municipal, no PDFs descargados ni verificaciones independientes. La URL estable exige abrir «Cronologia informativa»; los enlaces AJAX efímeros no se publican como URLs documentales.

`fechas_acuerdo` y `fechas_publicacion` conservan todas las fechas encontradas en sus respectivos contextos. Los campos singulares quedan nulos si hay varias. En la entrada 1 se conserva también el acuerdo de cumplimiento de prescripciones; no se elige arbitrariamente una sola fecha de aprobación. La entrada 6 expresa conformidad con texto refundido, por lo que no se rellena `fecha_aprob`. `fecha` siempre queda nula. Se conserva el contexto original para interpretar cada acuerdo.

No hay geometría de los instrumentos verificada. `lat`, `lon` y `geometry` son nulos, `publication_ready=false`; no se reutilizan coordenadas de la casa consistorial. Licencias, programación y jitter están desactivados.

## Extracción, paginación y validación

El adaptador abre la página en una sesión HTTP nueva y sigue las acciones Wicket descubiertas en el HTML de esa sesión para ambos niveles de Cronologia informativa. El padre y el hijo publican el mismo inventario: se comparan y se emite una sola copia. Falla si cambian la estructura, aparecen controles de paginación, faltan ordinales, hay duplicados o aparecen instrumentos de formato desconocido. No hay límite de registros ni corte de páginas. El resultado se escribe de forma atómica tras validar ambas vistas; update vuelve a obtener la instantánea completa y no modifica un cursor.

Pruebas ejecutadas:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_campos -v
```

Cubren fechas catalanas y numéricas, separación entre aprobación y publicación, fechas múltiples, deduplicación de documentos, exclusiones, fallos de estructura/paginación, identidad independiente del ordinal, carga del manifest y licencias desactivadas.

La extracción real se ejecutó mediante `load_manifest('campos')`, `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `capture_dir='evidence'` como opción local. El cargador aplica además la política compartida de entidades: los seis registros quedan de categoría desconocida; no se fuerzan a una categoría inmobiliaria. Las evidencias locales no son fuente a incorporar al repositorio:

- `evidence/proyectos.jsonl`: seis registros reales.
- `evidence/validation.json`: recuento, fuentes, limitaciones y resultado de extracción.
- `evidence/live-inventory.html`, `live-chronology-0.xml`, `live-chronology-1.xml`: respuestas reales usadas por el adaptador.
- `evidence/parser-tests.txt`: salida de las pruebas.

No se acredita un inventario exhaustivo de obras físicas ni de licencias concedidas; el alcance es el planeamiento general identificado en esta cronología municipal.
