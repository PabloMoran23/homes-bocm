# Guadassuar — INE 46139, Valencia

Investigación y extracción real: 9 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Se revisaron primero `municipio/adapters/portal.py`, `municipio/manifest.py`,
`municipio/adapters/registry.py` y los manifests/adaptadores de Chipiona y Hernani.

## Fuentes oficiales y alcance

- Inventario municipal: https://www.guadassuar.es/urbanisme/ (redirige a
  https://guadassuar.es/urbanisme/). La entrada directa sin www dio 403 en la
  primera comprobación; www devolvió 200 tras redirección. No se usan caches
  de buscadores para la extracción.
- Identidad municipal: [Registro de Entidades Locales de la Generalitat](https://www.entidadeslocales.gva.es/index.php?id=46139&lang=es&option=com_reglocal_entloc&task=muestraEntidad&tipo=1),
  municipio de Guadassuar, código 46139, provincia de Valencia.
- Se descubrieron también la [oficina virtual](https://ov.guadassuar.es/) y la
  [sede electrónica](https://guadassuar.sede.dival.es/catalogoservicios.aspx?ambito=2&area=1543).
  Sus trámites de solicitud no constituyen un inventario de concesiones.

El adaptador recorre íntegramente los acordeones de las secciones 01 (planeamiento
en tramitación) y 02 (planeamiento aprobado). El contenido plegado ya está en el
HTML: no requiere clicks, API ni paginación. No hay límite de registros ni corte
por cantidad. Se rechazan controles de paginación conocidos, nuevos grupos no
reconocidos, instrumentos sin documentos y desaparición de secciones obligatorias.
No se recorre el listado de noticias de la sección 03: actualmente muestra dos
solicitudes de licencia ambiental, sin prueba de concesión. Tampoco se extraen
formularios, normas de presentación, contratación ni noticias generales.

## Resultado y agrupación

Extracción viva mediante el adaptador cargado desde el manifest: **8 instrumentos,
82 enlaces PDF**, sin registros precargados:

| Instrumento | Documentos |
| --- | ---: |
| PRI-I1 «La Garrofera», en tramitación | 14 |
| Modificación número 9 del PGOU, en tramitación | 7 |
| PGOU, incluidos tomos, planos, anuncios y corrección de errores | 43 |
| Modificación 1 del PGOU | 1 |
| Modificación 5 del PGOU | 2 |
| Modificación 6, Tanatori | 2 |
| Modificación 7, Trinquet | 4 |
| Modificación 8, incluidos acuerdos y correcciones de 2026 | 9 |

Los documentos del PGOU se agrupan en una sola entidad. Cada modificación se
agrupa por su número; los anexos del PRI y la modificación 9 pertenecen a su
respectivo instrumento. Se conservan nombres y enlaces directos de todos los
PDF, además de la URL del inventario y el ancla del acordeón de procedencia.
La corrección de errores no genera un proyecto independiente. Los enlaces se
codifican para conservar espacios y caracteres acentuados en rutas válidas.

## Fechas, procedencia y límites

`situacion_inventario` reproduce la clasificación del Ayuntamiento; no certifica
vigencia jurídica ni ejecución material. No se extraen fechas del CMS ni se
convierten fechas de nombres de archivo en fechas de acuerdo, aprobación o
publicación. Los acuerdos, anuncios y registros RAIPU se conservan como documentos
separados, dentro de su instrumento.

Como contraste documental, el [BOP de 9 de septiembre de 2025](https://bop.dival.es/bop/downloads?anuncioNumReg=2025%2F10459&lang=es)
identifica la aprobación definitiva de la modificación 8 y distingue esa publicación
del acuerdo plenario de 11 de julio de 2025. Estas fechas no se incorporan mediante
constantes: el adaptador no analiza texto de PDF. Tampoco se confunden con los
acuerdos anteriores o las correcciones de 2026 del mismo expediente.

Cobertura parcial del inventario documental de planeamiento, no un censo de obras,
licencias o todos los expedientes municipales. No se inventan referencias de
expediente, coordenadas ni fechas. `publication_ready=false` y
`geometry_status=unavailable`; programación, licencias y jitter desactivados.
La política compartida aplicada por el cargador clasifica los ocho registros como
`pendiente / insufficient_identity_evidence`: no se inventa una referencia literal
para superar ese control ni se afirma elegibilidad para actividad o publicación.

## Validación reproducible

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_guadassuar -v
```

Ocho pruebas pasan: agrupación y aislamiento, deduplicación, exclusión de trámites,
semántica sin fechas inventadas, contenido vacío, documentos ausentes, nuevos grupos,
paginación, procedencia inesperada, contrato backfill/update y manifest.

La ejecución real utilizó `load_portal_adapter(load_manifest('guadassuar'))` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, sin servicios de publicación.
`evidence/validation.json` contiene recuentos, URLs, limitaciones, resultado de la
política compartida y comprobaciones documentales. `evidence/urbanisme-live.html`
es la respuesta HTML capturada durante esa misma llamada real (el envoltorio de
captura guardó la respuesta de requests sin sustituirla por una fixture).

Se comprobaron 8 PDF, uno por instrumento, con petición Range 0–1023: todos dieron
HTTP 206 y firma `%PDF-`. Se guardan primeros bytes y metadatos en evidence; no se
han descargado ni leído íntegramente todos los documentos. Los enlaces restantes
están preservados, sin afirmar su verificación binaria individual. Toda la evidencia
es local y queda fuera de los cuatro archivos fuente.
