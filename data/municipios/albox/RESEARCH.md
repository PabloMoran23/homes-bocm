# Albox (04006), Almería

Investigación y extracción en vivo: 7 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales descubiertas

- [Normas del Ayuntamiento, alojadas en Dipalme](https://www.dipalme.org/Servicios/cmsdipro/index.nsf/informacion.xsp?documentId=EE9FBE10839CFBD0C1258162002AA3A5&p=Albox): responde HTTP 200 y enlaza la sección Urbanismo.
- [Inventario Urbanismo municipal](https://www.dipalme.org/Servicios/cmsdipro/index.nsf/informacion.xsp?documentId=31F247FAB5E8FCD7C1257846004AB10E&p=Albox): fuente del adaptador, HTTP 200. La cabecera identifica Ayuntamiento de Albox y el pie Albox (Almería), CIF P-0400600-C. Contiene los documentos de planeamiento y sus enlaces directos, sin paginación observada.
- [Web municipal alternativa](https://ayuntamientodealbox.com/) y [su sección BOP](https://ayuntamientodealbox.com/bop/): aparecen en búsqueda, pero ambas consultas HTTP directas dieron 403. No se utiliza su contenido indexado como sustituto de extracción en vivo.
- Los documentos del inventario se alojan en `www.dipalme.org/Servicios/Anexos/Anexos.nsf`, `www.dipalme.org/Servicios/Informacion/Informacion.nsf` y `www.albox.es/Servicios/Anexos/Anexos.nsf`. Se retiene el enlace original y se proporciona su variante HTTPS.

## Cobertura y agrupación

Se extrae la totalidad de los enlaces PDF de este inventario, agrupados en siete registros:

| Registro | Documentos únicos |
| --- | ---: |
| Estudio de detalle de alineaciones y rasantes sectores 7 y 8 | 3 |
| Estudio de detalle de alineaciones Avda. Lepanto | 2 |
| PGOU: documentación de alineaciones y alturas | 6 |
| Modificación PGOU Plaza Mayor | 1 |
| Modificación de normas de planeamiento y generales de edificación | 1 |
| Modificación artículo III.4, suelo no urbanizable | 1 |
| Adaptación del PGOU a la LOUA | 5 |

Son instrumentos/documentación de planeamiento reales, no obras adjudicadas ni licencias. El registro de alineaciones y alturas representa el conjunto cartográfico del PGOU, no seis proyectos de construcción independientes. El inventario repite `03_ORDENACION-TERMINO-MUNICIPAL.pdf` y `MEMORIA_APL_PGOU_08.pdf`; se deduplican por URL. La ficha justificativa de accesibilidad permanece con el estudio de sectores 7 y 8 según su posición en el inventario. La modificación de normas y la modificación posterior sobre suelo no urbanizable se separan: no son el mismo instrumento.

Se descargaron y conservaron para inspección cinco PDF y su texto mediante `pdftotext`, ya disponible en el sistema:

- `evidence/doc-3.pdf`: certificado del estudio sectores 7 y 8; sesión del 30 de junio de 2022 y firma del 6 de julio de 2022.
- `evidence/doc-5.pdf`: certificado del estudio Avda. Lepanto; misma sesión y fecha de firma.
- `evidence/doc-12.pdf`: BOP número 39, publicado el 25 de febrero de 2022; acuerdo de aprobación definitiva de Plaza Mayor del 7 de febrero de 2022.
- `evidence/doc-13.pdf`: modificación de normas; portada «Documento para la Aprobación Definitiva», febrero de 2009.
- `evidence/doc-14.pdf`: modificación artículo III.4; portada «Documento para la Aprobación Definitiva», septiembre de 2013, distinta del documento de normas de 2009.

Estas comprobaciones confirman la naturaleza y agrupación de los documentos. El adaptador extrae el inventario HTML y conserva enlaces; no incorpora un parser PDF ni fechas fijas extraídas manualmente. Todos los campos de fechas y fase quedan nulos. Una fecha de firma, un mes de redacción o la frase «para aprobación definitiva» no se convierten en fecha de aprobación. Tampoco se confunde la fecha del BOP con la del acuerdo.

## Límites y comportamiento

Cobertura parcial municipal: no pretende agotar expedientes históricos, otros tablones, BOP, obras o licencias del municipio. No se extraen formularios, anuncios de contratación o noticias como proyectos. No se afirma que todos los documentos del inventario constituyan el texto consolidado actualmente vigente. Los PDF están enlazados, y solamente los cinco indicados se descargaron e inspeccionaron durante esta investigación. No hay geometría verificada: coordenadas nulas, `publication_ready=false`, sin jitter.

Inventario de una sola página: backfill y update efectúan una lectura completa. Si aparecen controles de paginación, un nuevo adjunto no reconocido, origen documental inesperado, enlaces nuevos en el cuerpo del inventario o desaparece el contenido esperado, se produce un error para revisión en vez de truncar o escribir un éxito vacío. No hay límites de registros ni cortes por fecha. Los ID dependen del instrumento, no del orden de los enlaces. La escritura se completa mediante sustitución de un archivo temporal.

El manifest mantiene `schedule.enabled=false`, `geocode.jitter_missing=false`, `licencias.enabled=false`. No se modificaron fuentes compartidas ni dependencias.

## Validación reproducida

Pruebas: `python -m unittest municipio.test_albox -v`: 4 pruebas correctas (agrupación, duplicados, instrumentos distintos, fechas nulas, fallo ante cambio/paginación y contrato de carga/update/licencias deshabilitadas).

Extracción real mediante `load_manifest('albox')`, `load_portal_adapter(manifest)` y `adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `manifest.portal.config['capture_dir']='evidence'`. Resultado: **7 registros, 19 documentos únicos**. El wrapper compartido añade su anotación semántica; informa siete categorías desconocidas, sin bloqueo. Se conservan los instrumentos bajo `tipo=planeamiento_urbanistico` sin inventar categorías de actividad.

Evidencia local: `evidence/proyectos.jsonl`, `evidence/validation.json`, capturas HTML `urbanismo.html`, `normas.html`, `homepage.html`, `bop.html` y los cinco PDF/textos citados. `validation.json` incluye número de registros vivos, URLs de fuente y limitaciones. La evidencia no forma parte de los cuatro archivos fuente que se entregan.
