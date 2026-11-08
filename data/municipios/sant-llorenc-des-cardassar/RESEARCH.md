# Sant Llorenç des Cardassar — INE 07051

Verificado el 2026-11-08. Municipio de Illes Balears, comunidad autónoma Illes
Balears. Adaptador único para instrumentos municipales de planeamiento publicados
por el Govern de les Illes Balears (CAIB), Servei d'Avaluació Ambiental.

## Descubrimiento y fuentes oficiales

Se revisaron primero `municipio/manifest.py`, `municipio/adapters/portal.py`, el
registro de adaptadores y los ejemplos Hernani y Manlleu con sus manifiestos.

La página municipal [Urbanisme](https://www.santllorenc.es/arees/urbanisme)
remite a formularios de obras, MUIB y al visor cartográfico del Consell de Mallorca
<https://ide.conselldemallorca.cat/visor/arxurb/>. Los formularios no acreditan
concesiones. El inventario arqueológico enlazado no se convierte en proyectos.

Se recorrieron también las secciones oficiales de transparencia:

- [Acció de govern](https://portaltransparencia.santllorenc.es/temes/accio-de-govern-i-normativa/).
- [Normativa d’urbanisme](https://portaltransparencia.santllorenc.es/temes/accio-de-govern-i-normativa/urbanisme/normativa-durbanisme/): enlaces a Urbanismo y certificados de regulación general; no se extraen como proyectos.
- [Plans i programes](https://portaltransparencia.santllorenc.es/temes/accio-de-govern-i-normativa/normativa-plans-i-programes/plans-i-programes-destacats-sobre-politiques-publiques/): inversiones presupuestadas, programación contractual, PRTR y juventud; no se convierten automáticamente en obras.
- [Documents oficials](https://seue.santllorenc.es/ca/documents-oficials): interfaz dinámica y árbol público `/api/categorias-front`; la categoría Urbanisme pertenece a modelos/solicitudes.

El tablón enlazado por la sede es
<https://ovac.santllorenc.es/eMiServicio/catala/Externos/ASP/enlacesPortada/EnlacesPortadaSede.asp?enlacePortada=tablon>;
la conexión HTTPS fue rechazada desde este entorno. No se presupone su contenido.

La búsqueda de fuentes oficiales de evaluación ambiental permitió encontrar el
portal CAIB y revisar su archivo de acuerdos desde junio de 2023. Desde su
navegación se descubrieron los **dos inventarios usados por el adaptador**:

1. [Documentos ambientales en evaluación simplificada](https://www.caib.es/sites/serveiassessoramentambiental/ca/publicacio_de_documents_ambientals_en_tramitacia_davaluacia_simplificada/).
2. [Documentos iniciales en evaluación ordinaria](https://www.caib.es/sites/serveiassessoramentambiental/ca/publicacia_de_documents_inicials_en_tramitacia_davaluacia_ordinaria/).

Ambos respondieron HTTP 200. Se analiza exclusivamente `main
.imc--contenido-html`, evitando duplicados y expedientes ajenos presentes en el
menú global. Se siguen los enlaces relativos `contenido.do?idsite=7085&cont=...`
**respecto de la URL completa del inventario**, y las redirecciones llevan a los
detalles canónicos. Las URLs relativas `archivopub.do` se resuelven respecto del
detalle. Se conserva la URL de descubrimiento y la procedencia de cada documento.

## Cobertura comprobada

La extracción real produce **8 instrumentos / 23 documentos**, siete del
inventario simplificado y uno del ordinario. Referencias del procedimiento
ambiental (no números municipales de licencia):

| Expediente CAIB | Instrumento descrito por el detalle | Documentos |
| --- | --- | ---: |
| 113e/2025 | Modificación 19 de normas subsidiarias | 2 |
| 132e/2025 | Modificación 39, ampliación de equipamientos de depuración | 2 |
| 134e/2026 | Modificación 38, Cala Millor: sistema hidráulico, espacios libres y aparcamiento | 3 |
| 230e/2024 | Ordenación del sistema general de la deixalleria de Son Carrió | 2 |
| 263e/2024 | Modificación 35, delimitación de suelo industrial | 6 |
| 27e/2023 | Modificación 32, sistema viario para el vial cívico hacia la vía verde | 3 |
| 30e/2023 | Ordenación del sistema general de la deixalleria de la zona costera | 2 |
| 53e/2023 | Modificación 33, ampliación de equipamientos de depuración | 3 |

Se agrupan memorias, estudios ambientales, movilidad y planos por expediente;
ningún documento adicional genera otra actuación. Se deduplican documentos por
identificador oficial de archivo. Los ID de registro derivan de la referencia
CAIB, no del texto del título. Se conserva el título del índice y del detalle.
**113e/2025 tiene una discrepancia oficial**: el índice dice modificación 9 y el
detalle dice 19. `discrepancia_titulo=true` lo señala sin corregir la fuente.

Se excluyen todos los expedientes A de impacto ambiental, incluidos proyectos
energéticos, agroturismos y el proyecto de deixalleria. El alcance elegido es
planeamiento estratégico E, no todos los proyectos ni todas las obras del término.
Los dos expedientes de deixalleria de la tabla son instrumentos de ordenación
con referencias distintas; no se crean además registros por sus documentos.

## Semántica y límites

La presencia en estos inventarios acredita publicación de documentación ambiental,
no aprobación municipal, concesión de licencia, vigencia del plan ni permanencia
de una consulta abierta. `procedimiento_ambiental` identifica el inventario;
`fase` permanece nula. No se extraen fechas de los años de referencia, del pie de
página ni de los metadatos HTTP. `fecha`, `fecha_publicacion`, `fecha_acuerdo` y
`fecha_aprob` son nulas: las páginas revisadas no las explicitan. Los PDF se
conservan como documentos fuente; este adaptador no interpreta sus acuerdos.

`source=caib` y `organismo_fuente` identifican al editor autonómico. El manifiesto
usa `proyectos.source=ayuntamiento` para seleccionar el flujo de adaptador directo
del esquema existente, no para atribuir al ayuntamiento la edición de estas páginas.

Cobertura parcial de los inventarios actualmente publicados, con referencias
2023–2026 en esta extracción; no se garantiza exhaustividad histórica o municipal.
No existe paginación activa en las dos páginas revisadas. Se leen completas, sin
límite de filas; si aparecen controles de paginación el adaptador falla de forma
explícita y exige revisar el recorrido. También falla ante cambio de estructura,
identidad incompatible, enlaces documentales desconocidos o ausencia total de
registros/documentos. No reemplaza el JSONL anterior hasta completar ambas fuentes.
Un instrumento repetido entre ambos procedimientos requiere revisión, sin fusionar
versiones automáticamente. `update_proyectos` refresca la instantánea completa.

### Geometría

`geometry_status: unavailable`. Hay planos PDF, pero no se ha verificado una capa
vectorial vinculada por expediente en MUIB o en el visor del Consell. No se
vectorizan planos ni se usan coordenadas del ayuntamiento como ubicación de los
planes. Latitud, longitud y geometría nulas; `publication_ready=false`.

## Validación y reproducción

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_sant_llorenc_des_cardassar -v
```

Seis pruebas pasan: filtros territoriales y de procedimiento, exclusión del menú,
deduplicación y agrupación, discrepancia de títulos, fechas desconocidas,
clasificación como expediente, rechazo de paginación/identidad/markup alterados,
refresco de ambas fuentes, conservación del archivo ante error y manifiesto.

La ejecución real usa `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
`manifest.portal.config['capture_dir']='evidence/live-captures'`. La anotación
compartida de entidades también se ejecuta. Evidencia local no versionada:

- `evidence/proyectos.jsonl`: registros reales y documentos enlazados.
- `evidence/validation.json`: recuento, URLs, runtime, pruebas y limitaciones.
- `evidence/live-captures/`: las dos páginas de inventario y ocho detalles de esa ejecución.
- Capturas de descubrimiento en `evidence/*.html` y `categories.json`.
- `evidence/documents-checked.json` y memorias PDF de 27e/2023 y 113e/2025: HTTP 200, tipo application/pdf y firma `%PDF-` comprobados. No se afirma haber descargado los otros 21 documentos.

Sólo cuatro archivos fuente nuevos. Sin cambios compartidos ni dependencias.
Licencias y programación deshabilitadas, `geocode.jitter_missing=false`.
