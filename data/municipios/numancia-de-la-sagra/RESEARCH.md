# Numancia de la Sagra — Toledo — INE 45119

Comprobación en vivo: 2026-11-09. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuente oficial y descubrimiento

La [portada municipal](https://www.ayuntamientonumanciadelasagra.com/) enlaza
«Información urbanística» en su navegación. El extractor parte de ese
[inventario municipal](https://www.ayuntamientonumanciadelasagra.com/informacion-urbanistica/),
no de una noticia ni de PDFs precargados. Sigue los enlaces de instrumentos
descubiertos en el inventario y conserva todos los PDFs de sus páginas de detalle:

| Instrumento | Fuente | Documentos en vivo |
| --- | --- | --- |
| Modificación puntual nº 12 de las NNSS | Inventario principal | 4: documento ambiental y tres tomos técnicos |
| Modificación del plan parcial del sector 7 | [Subinventario del plan parcial](https://www.ayuntamientonumanciadelasagra.com/Modificacion_Plan_Parcial/) | 16, más propuesta de convenio enlazada desde el inventario principal como contexto del sector |
| Modificación del proyecto de urbanización del sector 7 | [Subinventario del proyecto](https://www.ayuntamientonumanciadelasagra.com/Modificacion_Proyecto/) | 40: memoria, presupuesto, seguridad, electricidad y planos |

Resultado: **3 instrumentos reales, 61 enlaces documentales**. Cada documento
retiene título, URL y página de procedencia. Memorias, planos, tomos, presupuestos
y estudios auxiliares no generan proyectos adicionales. Plan parcial y proyecto
de urbanización son instrumentos diferentes del mismo ámbito. La propuesta de
convenio no se interpreta como convenio aprobado ni como actuación independiente.

Las tres páginas respondieron HTTP 200. Se descargó y comprobó la firma `%PDF-`
de un documento principal de cada instrumento; las primeras cinco páginas se
extrajeron localmente con `pdftotext` para confirmar su contenido:

- [Documento inicial estratégico MP12](https://www.ayuntamientonumanciadelasagra.com/wp-content/uploads/2022/12/DIE_MODIF_N12_NNSS_NUMANCIA.pdf): identifica la modificación y al municipio; documento de marzo de 2019.
- [Memoria del plan parcial S7](https://www.ayuntamientonumanciadelasagra.com/wp-content/uploads/2022/12/MemoriaJustificativa2019.pdf): identifica la modificación del plan parcial de mejora del sector 7; documento de octubre de 2019.
- [Memoria de urbanización S7](https://www.ayuntamientonumanciadelasagra.com/wp-content/uploads/2022/12/Proyecto_Urbanizacion/Memoria_Proyecto_Sector_7.pdf): describe pavimentación, saneamiento, abastecimiento y otras redes del proyecto modificado de octubre de 2019.

La página de urbanización repite por error el encabezado del plan parcial. La
clasificación procede del enlace del inventario y queda corroborada por su memoria,
no del encabezado repetido. No se ha verificado la descarga de los otros 58 adjuntos.

## Semántica y cobertura parcial

Se extrae el inventario documental accesible hoy, que contiene documentación
histórica; no constituye un catálogo consolidado de planeamiento vigente. Las
fechas de redacción o firma de 2019 y la carpeta de subida `2022/12` no acreditan
publicación municipal, aprobación ni concesión. `fecha`, `fecha_publicacion`,
`fecha_acuerdo`, `fecha_aprob` y `fase` quedan nulas. Tampoco se infiere ejecución
de las obras o titularidad pública a partir de una memoria de urbanización.

El sector 8 aparece como texto, sin enlaces a sus documentos: no se emite un
registro. Se excluyen los estatutos de entidades de conservación, formularios,
noticias y anuncios de contratación. No hay un registro de licencias concedidas
verificado; los métodos de licencias producen un archivo vacío y estado disabled.

La investigación identificó también la
[sede electrónica](https://ayuntamientonumanciadelasagra.sedelectronica.es/),
publicaciones de BOP Toledo y acuerdos autonómicos. No se integran en este
adaptador ni se trasladan sus fechas al inventario histórico. Esa ampliación
requiere reconciliar versiones y actos con sus instrumentos. La portada municipal
contiene además texto ajeno sobre casinos: no se utiliza como contenido de
proyectos ni se siguen sus enlaces externos.

## Paginación, geometría y actualización

No se observó paginación en ninguno de los tres inventarios; se recorren todos sus
enlaces documentales sin límite por número de registros. Si aparecen controles o
enlaces de paginación, el parser falla explícitamente para exigir revisión. También
falla ante pérdida de la estructura principal, instrumentos esperados, documentos
MP12 o detalles vacíos, y ante enlaces documentales a otro dominio. Una nueva
familia de instrumentos requiere ampliar y revisar el parser. Las actualizaciones
son instantáneas completas, sin fingir disponer de histórico incremental.

`geometry_status: unavailable`: las fuentes revisadas proporcionan planos PDF,
sin geometría vectorial verificada y vinculada a estos instrumentos. No se han
georreferenciado planos ni asignado coordenadas de centroide municipal.
`lat`, `lon` y `geometry` nulos; `publication_ready: false`.

## Validación reproducible y evidencia local

`python -m unittest municipio.test_numancia_de_la_sagra -v`: **5 pruebas pasan**.
Cubren agrupación y deduplicación documental, procedencia, exclusión de estatutos
y sector sin documentos, fechas y coordenadas nulas, detección de paginación,
cambios de estructura, dominio inesperado y carga mediante manifest/registry.

Extracción real ejecutada con `load_portal_adapter(load_manifest(...))` y
`backfill_proyectos`, configurando únicamente `evidence_dir` para las capturas.
La política compartida anota los tres registros como `unknown`: no se altera esa
política ni se inventa una referencia de expediente para eludirla. Este resultado
documental requiere revisión independiente y no implica publicación autorizada.

Evidencia local, excluida del código fuente: `evidence/proyectos.jsonl`,
`evidence/validation.json`, `evidence/tests.txt`, capturas HTML y tres PDFs con
extractos de texto. `validation.json` registra conteo, URLs, comprobaciones PDF,
límites de cobertura y anotación de la política. No se ejecutó ningún paso de
publicación, base de datos o despliegue.

Manifest: `schedule.enabled=false`, `geocode.jitter_missing=false`,
`licencias.enabled=false`; municipio y provincia explícitos.
