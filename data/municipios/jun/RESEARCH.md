# Jun — Granada — INE 18111

Investigación y extracción en vivo: 9 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales actuales

La [sede municipal](https://ayuntamientojun.sedelectronica.es/) identifica a Jun,
enlaza el tablón, el portal de transparencia y el perfil de contratación.
Se recorrió transparencia → 7. Urbanismo → 7.1. Planeamiento urbanístico:

- [Inventario de planeamiento](https://ayuntamientojun.sedelectronica.es/transparency/b12db815-40c7-4e1f-a3a4-4d473bf4cdec/).
  Contiene el registro de entidades colaboradoras (excluido) y una carpeta de
  instrumento con cuatro documentos.
- [Innovación del PGOU-AP NN.SS. UE-2 y suelos derivados de UE-1](https://ayuntamientojun.sedelectronica.es/transparency/92ce359e-78b1-42cd-8677-f57c4c04f8a1/).
  Se genera **un registro**, conservando los cuatro enlaces: MRVIS, anuncio del
  avance/borrador del expediente 370/2024, DAE y documento urbanístico de junio de
  2024. Cada ficha documental devolvió HTTP 200 y un visor PDF. Los títulos no
  prueban aprobación definitiva ni vigencia del instrumento. No se convierten
  «junio 24», fechas de creación del CMS o fechas de documentos en acuerdos.
- [Tablón vigente](https://ayuntamientojun.sedelectronica.es/board): siete anuncios
  en la consulta observada, uno relativo a una actuación física identificable.
  [Anuncio de aprobación del proyecto 2024/4/PPCGR/1-26](https://ayuntamientojun.sedelectronica.es/preview-document/b653235d-9fe6-4503-bfb7-a786ff734666),
  C.P. GR-3103 Granada–Alfacar, mejora de intersección en P.K. 1+290.
  Expediente municipal de publicación 205/2026. Se genera **un registro**.

El anuncio de carretera procede de la Delegación de Obras Públicas y Vivienda de
la Diputación de Granada, publicado por el Ayuntamiento. Se descargó y examinó
el PDF íntegro (111662 bytes, HTTP 200, `application/pdf`, firma `%PDF`); su tabla
identifica terrenos afectados en el término de Jun. El texto dice aprobación
definitiva de **27/02/2026**; firma de 18/03/2026 y registro de salida de
19/03/2026. El tablón municipal indica publicación **20/03/2026**. El adaptador
extrae solo esta última como `fecha_publicacion`: no analiza el texto PDF para
extraer fechas de acuerdo. La aprobación no se interpreta como ejecución de obra
ni como licencia municipal concedida.

También se comprobó la web `https://ayuntamientojun.org/`, que devolvió 403 en
esta ejecución. El apartado municipal 7.4 Obras públicas e infraestructuras
mostraba cero documentos. Se localizaron anuncios de contratación de
pavimentaciones durante la búsqueda, pero no se usaron como proyectos. Tampoco
se incluyen formularios de licencia, bandos de limpieza, empleo ni elecciones.
La resolución ambiental de la Junta encontrada en la búsqueda no se incorpora
como otro instrumento duplicado ni como aprobación urbanística.

## Extracción y límites

Resultado vivo: **2 registros y 5 enlaces documentales**, sin registros
precargados. El adaptador lee el inventario de planeamiento, resuelve sus enlaces
Wicket de sesión a carpetas con URL estable, agrupa documentos por instrumento y
comprueba la cuenta declarada de documentos. Lee después la tabla completa del
tablón, seleccionando anuncios explícitos de aprobación de proyectos físicos.
Agrupa publicaciones de un proyecto por su código; conserva enlaces y fechas por
documento. Comprueba que las cinco fichas exponen un visor PDF. Los enlaces a
fichas son estables; no se guardan tokens efímeros como URL canónica.

No se observó paginación en ninguno de los listados utilizados. Si aparece un
paginador, el adaptador falla explícitamente; también falla ante estructura
incompatible, carpetas vacías o cuentas documentales incompletas. No hay un límite
que corte registros silenciosamente. `update_proyectos` reconstruye la instantánea
vigente; no mantiene un histórico de anuncios retirados.

Cobertura parcial: solo la sección 7.1 y anuncios de aprobación vigentes que
cumplen el selector; no se afirma cobertura total del urbanismo municipal, del
registro autonómico, obras ejecutadas ni histórico. No hay coordenadas, fases ni
fechas de aprobación inferidas. Los registros marcan `publication_ready: false`
y `geometry_status: unavailable`. Manifest con `licencias.enabled: false`,
`schedule.enabled: false` y `geocode.jitter_missing: false`.

## Validación reproducible

Pruebas: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_jun -v`
(**8 pruebas correctas**). Cubren exclusión de formularios/contratación/noticias,
semántica temporal, agrupación documental, aislamiento entre instrumentos,
paginación, discrepancias de cuentas, cambio de estructura y manifest.

Ejecución real directa, sin publicación, geocodificación ni base de datos:

```python
from pathlib import Path
from municipio.adapters.jun import JunAyuntamientoAdapter
from municipio.manifest import load_manifest
m = load_manifest('jun')
a = JunAyuntamientoAdapter(m.slug, {'evidence_dir': str(Path('evidence').resolve())}, m.portal.base_url)
result = a.backfill_proyectos(Path('evidence/proyectos.jsonl'))
```

Evidencia local, no destinada al commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, capturas HTML del descubrimiento y de cada petición
del adaptador (nombre SHA-256 de su URL), `evidence/project.pdf` y su transcripción
`evidence/project.txt`. El JSON de validación contiene `live_records: 2`, las ocho
URLs finales consultadas por el adaptador, limitaciones y comprobación del PDF.
