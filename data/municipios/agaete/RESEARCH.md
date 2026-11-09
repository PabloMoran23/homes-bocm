# Agaete — INE 35001, Las Palmas, Canarias

Investigación y extracción real: 9 de noviembre de 2026.

## Fuente oficial y alcance

Se revisaron primero el contrato `municipio/adapters/portal.py`, el cargador de manifests y los ejemplos Chipiona y Hernani. Se implementa únicamente Agaete, sin cambios compartidos.

Inventario seleccionado: [Planeamiento urbanístico de Agaete, SITCAN](https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-agaete), publicado por Política Territorial, Cohesión Territorial y Aguas del Gobierno de Canarias. Su descripción identifica al Gobierno de Canarias como productor y mantenedor y a GRAFCAN como responsable de normalización. Es una fuente autonómica oficial específica del municipio, no un inventario del ayuntamiento. El valor `proyectos.source: ayuntamiento` selecciona la ruta de adaptadores del esquema existente; los registros conservan `source: gobierno_de_canarias_sitcan`.

API pública utilizada:

https://opendata.sitcan.es/api/3/action/package_show?id=planeamiento-urbanistico-de-agaete

`package_show` entrega el conjunto completo de recursos de un paquete; no se usa una búsqueda paginada ni un límite de resultados. Se comprueban título/nombre municipal y `num_resources == len(resources)`. En esta ejecución: **27 recursos**, siete grupos documentales de origen, agrupados en **seis instrumentos**, con **287 enlaces PDF adicionales** obtenidos recorriendo íntegramente los siete índices de IDECanarias. Los índices no mostraron paginación. El parser rechaza controles de paginación, índices sin PDF, recursos inesperados o recuentos incompletos antes de reemplazar la salida.

Instrumentos realmente extraídos:

- Modificación puntual del PGO, Catálogo Arquitectónico CCA-40, Hotel Princesa Guayarmina: [índice 707](https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/Agte/707/indice.html).
- Revisión parcial del PGO, sector Las Candelarias: [índice 705](https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/Agte/705/indice.html).
- Plan Parcial SUSNO-1 Las Candelarias: [índice 727](https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/Agte/727/indice.html), con la [sentencia de anulación, índice 728](https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/Agte/728/indice.html) adjunta al mismo instrumento. Se advierte expresamente su carácter histórico y anulación; la sentencia no se convierte en otro proyecto.
- Plan Parcial Cruz Chiquita: [índice 657](https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/Agte/657/indice.html).
- Adaptación Básica del PGO: [índice 655](https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/Agte/655/indice.html).
- Modificación puntual del PGO, ámbito AUA-7: [índice AUA7](https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/Agte/rppgo_AUA7/indice.html).

Cada instrumento retiene todos sus recursos SIPU, FIP, índices y consultas GRAFCAN presentes, sus identificadores CKAN, títulos/descripciones originales y enlaces. El formato del catálogo puede decir PDF aunque el recurso sea un índice HTML: se conservan por separado `formato_catalogo` y `mimetype_catalogo`. Los PDF descubiertos llevan `source_url` del índice de procedencia y se restringen al directorio del instrumento. No se descargan íntegramente todos los PDF/ZIP ni se interpretan como proyectos independientes las memorias y planos.

## Fechas y límites

Las fechas `publicado el` de las descripciones se registran como `fecha_publicacion`, también en cada recurso que las expresa. Solo la mención explícita `por Pleno COTMAC el 28/07/2005` produce `fecha_acuerdo: 2005-07-28`; su publicación es 2005-09-16. Las fechas de creación/actualización del catálogo no son acuerdos ni aprobaciones. No se infieren fases ni fechas a partir de la frase genérica «Aprobación Definitiva».

La cobertura es histórica y parcial. El catálogo declara trabajos de sistematización de 2010–2015 y su modificación de metadatos observada es 2025-10-10. No representa todo el planeamiento actual: por ejemplo, se localizó el [BOC 2023/161, anuncio 2847](https://www.gobiernodecanarias.org/boc/archivo/2023/161/pda/017.html), relativo a Las Candelarias-Parcela 3, que no figura entre los 27 recursos de este paquete. También existe la [exposición autonómica del Plan Supletorio](https://www.gobiernodecanarias.org/planificacionterritorial/materias/exposicion-de-planes-y-normas/ambito-municipal/planes-supletorios/pgos_agaete/), fuera del alcance de este adaptador. No se completa el inventario con noticias, licitaciones o expedientes prefijados.

No hay coordenadas ni geometría verificada; `publication_ready: false`, `geometry_status: unavailable`, `geocode.jitter_missing: false` y `schedule.enabled: false`. La política compartida anota los seis registros como pendientes por falta de referencias de expediente reconocidas por sus reglas; se conserva esa anotación sin inventar números ni forzar elegibilidad. Los instrumentos están identificados por sus títulos y documentos oficiales. No se afirma ejecución física ni vigencia normativa actual. Licencias desactivadas: los formularios de la sede electrónica no acreditan concesiones.

## Validación reproducible

Runtime usado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_agaete -v`: **8 pruebas correctas**, sobre agrupación de sentencia, aislamiento de instrumentos, retención de formatos, fechas explícitas, identidad municipal, inventario incompleto, índices/documentos, rechazo de paginación y conservación de salida anterior ante fallo.

Extracción real mediante `load_manifest('agaete')`, `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`. Se activó únicamente `portal.config.capture_dir = 'evidence/captures'` en memoria para guardar respuestas públicas. La actualización vuelve a consultar el inventario entero; no usa un cursor que pudiera omitir modificaciones históricas.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`, `evidence/validation.json`, respuestas JSON/HTML bajo `evidence/captures/`, captura inicial `evidence/sitcan-package.json` y muestra `evidence/sample-pdf-prefix.bin`. Un PDF de la modificación CCA-40 respondió HTTP 200, `application/pdf`, firma `%PDF-`; solo se capturaron 1024 bytes. `validation.json` contiene URLs, recuentos, limitaciones y comprobación documental. No se ejecutaron publicación, base de datos, despliegue ni geocodificación.
