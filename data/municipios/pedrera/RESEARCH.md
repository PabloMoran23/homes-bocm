# Pedrera — investigación y alcance

Consulta y extracción en vivo: 9 de noviembre de 2026. Municipio Pedrera,
Sevilla, Andalucía; código INE `41072`. El portal municipal identifica su
Ayuntamiento y domicilio en Pedrera; el portal de transparencia publica el CIF
municipal P4107200J. No se han utilizado noticias como proyectos ni formularios
como licencias concedidas.

## Fuentes oficiales implementadas

- [PGOU municipal](https://www.pedrera.es/es/urbanismo/pgou/): inventario
  con el rótulo «DOCUMENTO DE APROBACIÓN PGOU SEPTIEMBRE DE 2015».
  Se extraen sus 13 enlaces: normas urbanísticas, dos fichas de planeamiento
  y diez planos. Constituyen **un instrumento**, no trece actuaciones.
  Los archivos son enlaces originales HTTP al alojamiento de la Diputación
  `multimedia.dipusevilla.es/pedrera/ficheros/archivos/pgou_2015/`.
- [Plan Básico de Ordenación Municipal](https://www.pedrera.es/es/ayuntamiento/encuesta-de-participacion-ciudadana/):
  pese al nombre histórico de la ruta, la página actual presenta el PBOM
  «FASE 3 AVANCE V2». Sus 50 documentos (PDF y DOCX) incluyen cuatro
  documentos de información/tramitación, cuatro memorias, 41 piezas de
  cartografía y el Documento Inicial Estratégico. Se agrupan como **un
  instrumento en avance**, conservando todos los enlaces y títulos.

Los dos inventarios son páginas únicas sin paginación observada. No se aplican
límites de registros ni de documentos. El parser rechaza controles de paginación,
ausencia de contenido, cambios de rótulo o destinos documentales ajenos al
ámbito revisado. Si aparece paginación será necesario revisar el recorrido antes
de ejecutar de nuevo: no se devuelve silenciosamente sólo la primera página.

## Otras fuentes descubiertas y límites

Se consultó también el [indicador 53 de transparencia: modificaciones y planes
parciales](https://transparencia.pedrera.es/es/transparencia/indicadores-de-transparencia/indicador/53.-Se-publican-y-se-mantienen-publicados-las-modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados.-00031/).
Incluye el borrador de modificación 3, innovación 5, Plan Parcial SUS-9.1,
convenio Getsemaní y documentación ambiental de modificación 2. Esta fuente
mezcla documentos y repite enlaces; **no está implementada**. Su captura
`evidence/modificaciones.html` permite revisar esa ampliación en otro trabajo.
La cobertura entregada es expresamente parcial: no se afirma que los dos
instrumentos extraídos sean todo el planeamiento de Pedrera.

Como contraste de investigación se localizaron las publicaciones oficiales
[BOJA 2015/175/9](https://www.juntadeandalucia.es/boja/2015/175/9)
(registro/publicación del PGOU aprobado parcialmente el 9 de febrero de 2015),
[BOJA 2015/214/13](https://www.juntadeandalucia.es/boja/2015/214/13)
(levantamiento de suspensión) y
[BOJA 2020/148/30](https://www.juntadeandalucia.es/boja/2020/148/30)
(modificación 1). No se extraen registros ni fechas de esos boletines. El rótulo
municipal de septiembre de 2015 se conserva como texto de procedencia: no se
convierte en una fecha exacta de acuerdo, aprobación o publicación.

No se extraen licencias, contratación, noticias, obras físicas ni modificaciones
como registros adicionales. Tampoco se certifica la vigencia jurídica del PGOU.
No se interpreta el contenido de los PDF/DOCX ni se verifica individualmente la
disponibilidad de los 63 archivos. No se generan coordenadas ni geometrías a
partir de planos o del domicilio del Ayuntamiento.

## Contrato, procedencia y validación

Se revisaron primero `municipio/manifest.py`, `municipio/adapters/portal.py`,
el registro de adaptadores y los ejemplos Chipiona y Hernani. El manifiesto
utiliza `codigo_ine: '41072'`, `licencias.enabled: false`,
`schedule.enabled: false` y `geocode.jitter_missing: false`.

El adaptador descarga ambos inventarios oficiales en cada backfill/update,
valida ambos antes de reemplazar la salida y conserva por instrumento los
`título/url/source_url` de cada documento, URL del inventario, momento de
recuperación UTC y SHA-256 de la respuesta. Los identificadores son estables
por instrumento, independientes del número y orden de sus documentos.
Las fechas desconocidas son nulas; no hay coordenadas ni inferencias de
aprobación definitiva a partir de etiquetas. `publication_ready` es falso.
La actualización es una instantánea completa, sin estado incremental.
Las operaciones de licencias fallan explícitamente por estar deshabilitadas.

Ejecuciones realizadas con el runtime preinstalado:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_pedrera -v
```

Resultado: seis pruebas correctas, incluyendo agrupación/deduplicación,
resolución de enlaces relativos, separación de fase y fechas, rechazo de
paginación y páginas inesperadas, fallo sin salida parcial y carga mediante el
registro real de adaptadores.

La extracción real se ejecutó con `load_manifest('pedrera')`,
`load_portal_adapter(manifest)` y `backfill_proyectos`, configurando
`capture_dir` a `evidence`. Resultado: **2 registros, 63 documentos**.
`evidence/proyectos.jsonl` contiene la salida real; `evidence/validation.json`
incluye `live_records`, URLs, procedencia y limitaciones. Las capturas de los
dos inventarios se guardan como `pgou.html` y `pbom.html`, con los bytes cuyo
hash registra la extracción. La política compartida se ejecutó mediante el
registro; no se modificó código compartido ni dependencias. La evidencia es
local y no forma parte de los cuatro archivos fuente entregados.
