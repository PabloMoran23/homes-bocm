# La Puebla del Río — INE 41079, Sevilla

Investigación y extracción real: 7 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y selección de fuentes

- [Urbanismo municipal](https://www.lapuebladelrio.es/es/urbanismo/): página actual con noticias, consulta previa del PGOU y noticias sobre contratación de redacción del PGOM. No se convierte una licitación, un formulario de consulta ni una noticia genérica en un proyecto o una licencia concedida.
- [Consulta previa](https://www.lapuebladelrio.es/es/urbanismo/consulta-pgou/): participación ciudadana; no registro de concesiones ni inventario de proyectos ejecutados.
- [Portal de transparencia](https://transparencia.lapuebladelrio.es/es/): lleva al inventario documental municipal seleccionado.
- [Indicador 50: planeamiento y planos](https://transparencia.lapuebladelrio.es/es/transparencia/indicadores-de-transparencia/indicador/50.-PLAN-GENERAL-DE-ORDENACION-URBANA-PGOU-Y-LOS-MAPAS-Y-PLANOS-QUE-LO-DETALLAN/): fuente HTML del adaptador. El contenido contiene instrumentos concretos con memorias, ordenanzas, cartografía y documentos ambientales. Se extraen los enlaces actuales, no una lista precargada de expedientes.

## Cobertura obtenida

| Instrumento | Documentos únicos |
| --- | ---: |
| Adaptación parcial del planeamiento | 23 |
| Normas Subsidiarias (NN.SS.) | 43 |
| PGOM (avance y documento previo a aprobación inicial) | 43 |
| POU (avance) | 27 |

Resultado vivo: **4 registros**, **136 enlaces documentales**. La adaptación y las NN.SS. son instrumentos distintos. Los documentos del avance del PGOM y los del documento previo a aprobación inicial se agrupan en un solo registro PGOM, conservando `version_documental` en cada documento. Los documentos del POU forman otro registro. No se generan proyectos independientes para cada plano, memoria, ordenanza o estudio ambiental. Los planos que ilustran modificaciones históricas dentro de las NN.SS. o su adaptación permanecen en su paquete documental, sin inventar expedientes independientes. Se excluye el apartado 50.3, ITACA, por ser un inventario toponímico.

La página contiene dos galerías cartográficas independientes: `pagegalleryfiles-1-2` (POU) y `pagegalleryfiles-2-2` (PGOM). Ambas tienen tres páginas. Se consulta la página base y las páginas 2 y 3 de cada galería: cinco peticiones en total, sin producto cartesiano de consultas. Las páginas 1 están incluidas en la base. Se descubren también los enlaces de páginas sucesivas en cada respuesta. El parser comprueba el marcador de página activa y deduplica por URL documental dentro de cada instrumento, reteniendo `inventory_urls` como procedencia. Si cambia el inventario de forma incompatible, falta un instrumento, falla una petición o se supera el límite de seguridad de 100 páginas, se produce error antes de reemplazar el resultado, sin presentar el recorrido incompleto como válido.

La galería «INFORME PARTICIPACIÓN AVANCE PGOM» está vacía en la respuesta observada: no se inventa un documento para ella. El adaptador sí agruparía sus enlaces PDF bajo PGOM si el ayuntamiento los publicase.

## Semántica y límites

Cobertura parcial del inventario del indicador 50, no censo completo de expedientes urbanísticos ni de obras físicas. La presencia actual de documentos no prueba su vigencia jurídica. «Documento previo a aprobación inicial» no significa aprobación inicial; «avance» tampoco significa aprobación definitiva. No se asigna una fase global al PGOM porque el registro conserva documentos de distintas versiones.

No se trasladan fechas históricas de las NN.SS. a la adaptación o al PGOM. No se extraen fechas de publicación, acuerdo o aprobación: no se han establecido inequívocamente por instrumento en este inventario. No se usan las fechas del CMS ni las de las noticias como fechas de acuerdo. No hay coordenadas verificadas y no se inventan. `publication_ready: false` y `geometry_status: unavailable` explicitan esa limitación. `schedule.enabled`, `geocode.jitter_missing` y `licencias.enabled` están desactivados. La política compartida añade su anotación al cargar el adaptador mediante el registro, sin modificar fuentes compartidas.

Se preservan los enlaces PDF, pero no se descarga ni interpreta todo su contenido. Se comprobó una muestra por instrumento: `Memoria.pdf`, `Memoria-de-Informacion.pdf`, `Avance-PGOM/1-Memoria/0-Resumen-ejecutivo.pdf` y `Avance-POU/1-Memoria/0-Resumen-Ejecutivo.pdf`, bajo la galería oficial `IND-50-`. Los cuatro respondieron HTTP 200, `application/pdf` y firma `%PDF-`. Solo se capturaron los primeros 8192 bytes de cada uno; esto no valida todas las páginas de esos documentos ni todos los enlaces del inventario.

## Validación reproducible

Pruebas offline (7 correctas):

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_la_puebla_del_rio -v
```

Cubren agrupación y versiones, exclusión de ITACA/formularios/enlaces externos, errores de estructura, paginación ignorada, recorrido completo y deduplicación, preservación del resultado anterior ante fallo y configuración del manifest/licencias desactivadas.

Extracción viva mediante el registro de adaptadores, sin publicación ni base de datos:

```python
from pathlib import Path
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter

manifest = load_manifest('la-puebla-del-rio')
manifest.portal.config['capture_dir'] = 'evidence/captures'
adapter = load_portal_adapter(manifest)
result = adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))
```

Evidencia local, fuera de los cuatro archivos fuente: `evidence/proyectos.jsonl`, `evidence/validation.json`, cinco capturas HTML en `evidence/captures/inventory-*.html` y cuatro muestras `*.pdf.partial`. La validación contiene `live_records`, URLs de todas las páginas consultadas, limitaciones, recuentos por instrumento, comprobaciones PDF y hashes de capturas. `update_proyectos` realiza una actualización íntegra del inventario actual, incluyendo cambios y desaparición de documentos; no afirma disponer de un histórico incremental completo.
