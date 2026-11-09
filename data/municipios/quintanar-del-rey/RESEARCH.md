# Quintanar del Rey — Cuenca — INE 16175

Verificación y ejecución real: 9 de noviembre de 2026. Identidad y código del municipio según el encargo; no confundir con Quintanar de la Orden (Toledo).

## Descubrimiento y fuentes

- [Web municipal](https://www.quintanardelrey.es/): actualmente muestra «Actualizando WEB», dirección Plaza Mayor, 1, Quintanar del Rey, Cuenca y enlaces a la sede electrónica. No ofrece actualmente un inventario municipal navegable de obras o planeamiento. Esta observación procede de la consulta web; un intento posterior de guardar el HTML con requests falló porque el servidor cerró la conexión, sin afectar a la fuente autonómica utilizada.
- [Portal de transparencia municipal](https://quintanardelrey.sedelectronica.es/transparency): consultado como fuente de descubrimiento; no se utiliza como registro de concesiones ni se afirma haber extraído su contenido completo.
- [Inventario oficial de acuerdos urbanísticos de la Junta de Comunidades de Castilla-La Mancha](https://urbanismo.castillalamancha.es/acuerdos-expedientes?title=Quintanar+del+Rey): fuente de extracción. Se usa su filtro público `title=Quintanar del Rey` y se verifica además el campo de población de cada tarjeta. El catálogo indica expresamente «Fecha del acuerdo». Aunque el HTML contiene avisos de Drupal en los filtros de taxonomía, el filtro de título devuelve siete resultados y las siete tarjetas completas. La página inicial sin filtro también se inspeccionó para identificar la paginación real, mediante enlaces `rel=next`.

## Cobertura observada

Las siete entradas filtradas contienen cuatro acuerdos de modificaciones numeradas del POM y tres expedientes de calificación urbanística. Estos últimos se excluyen del alcance elegido, sin considerarlos licencias municipales concedidas.

Se obtienen **tres instrumentos**, agrupando todos los documentos/acuerdos encontrados de una misma modificación:

| Instrumento | Acuerdo según catálogo | Documentos oficiales |
| --- | --- | --- |
| Modificación puntual 5 del POM | CCI, 03/10/2019 | [doc06527220191003120953.pdf](https://urbanismo.castillalamancha.es/sites/default/files/expedientes/doc06527220191003120953.pdf) |
| Modificación puntual 6 del POM | CCI, 25/03/2019; CPOTU Cuenca, 10/05/2019 | [ayuntamiento_quintanar_del_rey.pdf](https://urbanismo.castillalamancha.es/sites/default/files/expedientes/ayuntamiento_quintanar_del_rey.pdf), [punto_2_1.pdf](https://urbanismo.castillalamancha.es/sites/default/files/expedientes/punto_2_1.pdf) |
| Modificación puntual 8 del POM | CPOTU Cuenca, 31/07/2020 | [punto_2_quintanar_del_rey.pdf](https://urbanismo.castillalamancha.es/sites/default/files/expedientes/punto_2_quintanar_del_rey.pdf) |

Los cuatro PDF se descargaron realmente con HTTP correcto y firma `%PDF`, y se guardaron localmente con tamaños y SHA-256 en la validación. Tres son escaneados sin texto extraíble con `pdftotext`; no se ha realizado OCR. El documento de la modificación 8 sí contiene texto: notifica el acuerdo de la sesión de 31 de julio de 2020 y advierte que consta en el borrador del acta, sin perjuicio de su posterior aprobación. El adaptador extrae exclusivamente metadatos del inventario; no intenta interpretar automáticamente los PDF ni convertir una mención al trámite en una fase jurídica normalizada.

Cobertura **parcial**, del inventario autonómico filtrado por título, no un catálogo íntegro de planeamiento vigente, obras o historia municipal. No se generan registros adicionales del POM base o de modificaciones citadas incidentalmente en otros documentos. La última fecha de estos resultados es 2021 para las calificaciones excluidas; la última modificación seleccionada es de 2020. No se deduce que no existan actuaciones posteriores. Los modelos de solicitud, anuncios de contratación, noticias genéricas y expedientes de otros municipios no producen registros.

## Semántica y paginación

Cada registro identifica municipio, provincia, INE, organismo autonómico, URL del inventario, fichas oficiales y todos los enlaces PDF de sus acuerdos. Los IDs dependen del número de modificación del POM, no del orden de resultados. `source: ayuntamiento` conserva la convención de encaminamiento del repositorio; `organismo_fuente` y `origen` identifican expresamente que la publicación procede de la Junta.

`fecha_acuerdo` procede del campo correspondiente del catálogo; en instrumentos con varios acuerdos se conserva por acuerdo y el campo superior queda nulo. `fecha_publicacion` y `fecha_aprob` quedan nulos. No se inventan coordenadas, fechas, estado de ejecución o vigencia; `publication_ready: false`, geometría no disponible. No se asigna una fase a partir del tipo o del nombre de una comisión.

Se recorre `rel=next` hasta terminar, preservando el filtro de título, comprobando rangos continuos, total estable, URLs oficiales y ausencia de tarjetas duplicadas. Un ciclo, una página que repite el rango, la desaparición del contador o un total sin enlace siguiente producen error antes de escribir la salida. La ejecución observada muestra `1 - 7 de 7`, sin página siguiente. No hay límite silencioso de páginas o registros.

Licencias desactivadas: no se ha verificado un registro público de concesiones. `schedule.enabled=false` y `geocode.jitter_missing=false`. Actualización mediante una nueva instantánea completa, sin usar fechas de acuerdo como marcadores de publicación.

## Validación reproducible

Runtime preinstalado utilizado:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_quintanar_del_rey -v
```

Cinco tests correctos: agrupación y aislamiento de documentos, separación de fechas, exclusión de población incorrecta/formularios/contratos/calificaciones, rechazo de fuentes vacías o incompletas, seguimiento de paginación con filtro, rechazo de rangos repetidos y contrato del manifest/licencias desactivadas.

Se cargó el manifest mediante `load_manifest('quintanar-del-rey')` y el adaptador mediante `load_portal_adapter(manifest)`, con `capture_dir='evidence'`, y se ejecutó `backfill_proyectos(Path('evidence/proyectos.jsonl'))`. Resultado real: siete tarjetas examinadas, cuatro acuerdos seleccionados, tres registros. La anotación compartida de entidades devuelve estado `ok`; los tres registros quedan como entidad desconocida, sin atribuir promotores deducidos.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/inventory-live-0.html`, capturas del inventario inicial/filtrado y los cuatro PDF con sus extracciones de texto. La validación incluye `live_records`, `source_urls`, limitaciones y huellas de documentos. No se han utilizado bases de datos, publicación, instalación de software ni cambios compartidos.
