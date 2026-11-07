# Ansoáin / Antsoain — INE 31016, Navarra

Verificación y extracción directa: 2026-11-07, con el Python preinstalado
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y cobertura

La navegación de https://www.ansoain.es/ enlaza «Agenda 2030 y planes municipales»
y «Procesos participativos». Son inventarios oficiales actuales, con contenido
estático accesible sin credenciales. El extractor recorre todas las secciones de
ambas páginas, seleccionando instrumentos espaciales con documentos concretos:

- https://www.ansoain.es/ayuntamiento/agenda-2030/
- https://www.ansoain.es/procesos-participativos/

Resultado real: **4 instrumentos y 6 documentos PDF**. Cada instrumento conserva
sus documentos, su URL de inventario, su título original y su procedencia. No se
crea un registro por cada parte PDF.

| Instrumento | Documentos municipales | Alcance acreditado |
| --- | --- | --- |
| PMUS: Plan Movilidad Urbana Sostenible 2025 | [Parte 1](https://www.ansoain.es/wp-content/uploads/2026/01/PMUS_Antsoain_2025_F_P.COPIAA_Parte1.pdf), [Parte 2](https://www.ansoain.es/wp-content/uploads/2026/01/PMUS_Antsoain_2025_F_P.COPIAA_Parte2.pdf) | Plan sectorial espacial; sin acuerdo de aprobación verificado. Las partes son divisiones del archivo, no necesariamente de los capítulos. |
| Plan infraestructura verde de Ansoáin | [Parte 1](https://www.ansoain.es/wp-content/uploads/2024/06/PLAN-INFRAESTRUCTURA-VERDE-ANSOAIN-2023_Parte1.pdf), [Parte 2](https://www.ansoain.es/wp-content/uploads/2024/06/PLAN-INFRAESTRUCTURA-VERDE-ANSOAIN-2023_Parte2.pdf) | Plan sectorial espacial, con memoria y fichas; portada noviembre de 2023. No demuestra obra ejecutada ni aprobación urbanística. |
| PEAU parcela catastral 240, polígono 22, Ctra. Ansoáin 12, 2º | [Plan de participación](https://www.ansoain.es/wp-content/uploads/2026/05/Plan-de-participacion-ciudadana-ANSOAIN-PEAU_signed.pdf) | Instrumento concreto propuesto: modificación de determinaciones pormenorizadas del PGM; documento previo de participación. |
| PEAU modificación de usos pormenorizados y art. 27 de la normativa urbanística general | [Plan de participación](https://www.ansoain.es/wp-content/uploads/2025/08/20250818-PPC-USOS-POLIGONO-COMPLETO.pdf) | Propuesta de ordenación de usos del polígono industrial y modificación normativa, en participación previa según la página. |

Se revisaron las primeras tres páginas de cada PDF descargado con `pdftotext`.
Los PEAU incluyen el ámbito y la propuesta urbanística: son expedientes de
planeamiento identificados, no formularios para solicitar licencias. Su presencia
en el inventario no demuestra que el plazo de participación siga abierto hoy ni
que no hayan avanzado posteriormente en su tramitación.

**Cobertura parcial explícita**: no es inventario completo del planeamiento
vigente, del histórico municipal, de obras ejecutadas ni de licencias concedidas.
No se incluyen el PACES, el plan genérico de acción local, presupuestos
participativos, consultas normativas generales ni el tríptico de incendios. Tampoco
se convierten las licitaciones o noticias en obras o concesiones.

La página de transparencia de urbanismo
https://www.ansoain.es/transparencia/informacion-sobre-ordenacion-territorial-urbanismo-medio-ambiente-y-vivienda/
es principalmente una enumeración de obligaciones y remite al SIUN. El inventario
de Agenda 2030 ofrece un enlace actualizado a
https://administracionelectronica.navarra.es/SIUN_Consulta/Index.html#/inicio .
No se extrae SIUN ni se afirma cubrir el Plan General Municipal o sus modificaciones.
El catálogo de servicios de https://sedeelectronica.ansoain.es/catalogoservicios.aspx
contiene trámites de solicitud, sin acreditar concesiones; licencias deshabilitadas.

## Fechas y geometría

No se emiten `fecha`, `fecha_publicacion`, `fecha_acuerdo` ni `fecha_aprob`: las
secciones no acreditan fechas inequívocas de publicación o acuerdos. Las fechas
de redacción, los años del título, las reuniones de participación y las carpetas
de subida del PDF tienen significados distintos. Por ejemplo, el documento de la
parcela 240 muestra «MAYO 2025» y ref. 2518, aunque su URL está bajo `2026/05`.
Ninguno de esos datos se transforma en aprobación ni en fecha de publicación.

`geometry_status: unavailable`. Hay planos y fichas en los PDF, pero no se ha
verificado geometría vectorial asociada a estos cuatro instrumentos. El enlace
SIUN es un visor externo de consulta, no una geometría verificada para estos
registros. No se digitalizan planos ni se inventan coordenadas o CRS.
`schedule.enabled=false`, `geocode.jitter_missing=false`, `licencias.enabled=false`.
`publication_ready=false` expresa las limitaciones de geometría y verificación;
no implica que las fuentes sean ficticias.

## Comportamiento y validación reproducible

No se observa paginación en ninguno de los dos inventarios. El parser rechaza
controles de paginación, enlaces next/siguiente o páginas numeradas si aparecen,
para exigir una extensión del recorrido antes de admitir una extracción parcial.
No hay límite ni recorte del número de secciones. Una página vacía, contenido
HTML inesperado, un instrumento sin PDF, un plan dividido con partes faltantes,
una descarga fallida o un falso PDF abortan la extracción antes de reemplazar
la instantánea anterior. Una actualización vuelve a leer la instantánea completa;
no mantiene un historial de cambios ni escribe estado incremental.

Pruebas offline: `python -m unittest municipio.test_ansoain -v`, **6 pasan**.
Cubren agrupación de documentos, selección semántica y exclusión de formularios,
descubrimiento de nuevos PEAU, IDs repetibles, ausencia de fechas/coordenadas
inventadas, procedencia, paginación, pérdida de contenido, documentos no fiables,
partes incompletas, carga del manifiesto y conservación de la salida ante fallo.

La extracción en vivo se ejecutó a través de `load_manifest('ansoain')` y
`load_portal_adapter(...).backfill_proyectos(Path('evidence/proyectos.jsonl'))`,
configurando `portal.config.evidence_dir` sólo en memoria para guardar capturas.
Todos los PDF se descargaron, se comprobó la cabecera `%PDF-` y se calculó SHA-256.
Los IDs PEAU derivan del ancla de su sección; los planes sectoriales tienen una
clave estable por instrumento. No dependen de las URLs temporales de descarga.

Evidencia local no destinada a commit:
`evidence/proyectos.jsonl` (4 registros), `evidence/validation.json` (recuento,
URLs, limitaciones y mapa URL→captura con hashes), HTML de inventarios, seis PDF y
extractos de sus primeras páginas. Las capturas se nombran con los primeros 16
caracteres del SHA-256 de su URL. Se conservan también las capturas iniciales de
Agenda 2030, procesos y transparencia. No se han utilizado bases de datos,
publicación, despliegue ni cambios compartidos.
