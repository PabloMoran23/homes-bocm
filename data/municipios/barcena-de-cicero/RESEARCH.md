# Bárcena de Cicero (Cantabria), INE 39009

Investigación y ejecución real: 9 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales y alcance

Se revisaron primero `municipio/adapters/portal.py`, `municipio/manifest.py`, los
adaptadores y manifests de Chipiona y Hernani y el informe de Chipiona. Se añade
un único adaptador municipal, sin cambios compartidos ni dependencias nuevas.

1. [Urbanismo municipal](https://www.barcenadecicero.es/servicios-ciudadanos/urbanismo.html).
   Bajo el encabezado «NORMAS SUBSIDIARIAS DE BÁRCENA DE CICERO» hay seis enlaces:
   normas urbanísticas, memoria de información, memoria de ordenación y planos
   de calificación, clasificación y viarios. **Un instrumento**, no seis proyectos.
   Se conservan los títulos y las URL PDF originales, incluido el doble `/` en
   `/ftp//DOCUMENTOS/NNSS/`. No hay fecha de publicación o acuerdo verificable en
   ese bloque HTML y no se asigna ninguna. No se deduce vigencia del hecho de
   estar publicado en la web.
2. [Portada municipal](https://www.barcenadecicero.es/).
   El enlace destacado «PGOU EXPOSICIÓN PÚBLICA PGOU» descubre dinámicamente la
   [información pública de la modificación del PGOU aprobado provisionalmente](https://www.barcenadecicero.es/informacion-publica-de-la-modificacion-del-plan-general-de-ordenacion-urbana-aprobado-provisionalmente.html).
   Este conjunto se agrupa en **un segundo instrumento**: memoria, planos de
   información, planos de ordenación y resto de documentación. Los cuatro ZIP
   mantienen sus enlaces y procedencia; no se descomponen sus archivos internos.
   La ficha fecha su publicación el **21/04/2025**. Su texto identifica el acuerdo
   del **31/03/2025** como apertura de nuevo trámite de información pública.
   `fecha_acuerdo_tipo` conserva ese significado. La aprobación provisional del
   PGOU base de **28/06/2021** es un antecedente descrito literalmente en la fuente,
   conservado en `descripcion`; no es aprobación de la modificación ni aprobación
   definitiva. No se asigna `fecha_aprob`, `fase` ni un estado vigente deducido.

Ambas páginas documentales observadas son completas en una sola página, sin
paginación. El parser recorre todos los enlaces de cada bloque y elimina solo
URL duplicadas dentro del mismo instrumento. Si aparecen controles de siguiente
página o paginación, falla explícitamente antes de escribir. No se impone límite
de registros ni de documentos. La portada se usa para descubrir el conjunto PGOU,
no para declarar una cobertura completa de su archivo de noticias.

## Fuentes descartadas y límites

La [página municipal de trámites](https://www.barcenadecicero.es/tu-ayuntamiento/tramites.html)
publica solicitudes de licencia de obra, primera ocupación y otras instancias:
son formularios, **no concesiones**. `licencias.enabled` queda desactivado.

La búsqueda oficial también localizó la noticia municipal del PGOU de 2021,
que remite al tablón de la [sede electrónica](https://barcenadecicero.sedelectronica.es/info.0).
No se incorpora como un tercer instrumento ni se afirma haber recorrido todo el
tablón. La portada contiene noticias y anuncios, incluidos obras de La Maza y
arreglo de camino en Vidular; este adaptador no usa ese archivo como inventario,
ni convierte anuncios de contratación en actuaciones concedidas. No se reclama
cobertura de obras públicas, licencias ni todos los instrumentos municipales.

La cobertura es parcial: documentación de NNSS y conjunto PGOU enlazado actualmente
desde portada. No acredita vigencia, aprobación definitiva, ejecución, expedientes
históricos completos o estado actual del plazo de información pública de 2025.
No hay coordenadas fabricadas: `geometry_status=unavailable`,
`publication_ready=false`, `geocode.jitter_missing=false` y
`schedule.enabled=false`.

## Implementación y comprobación

El adaptador obtiene HTML real, valida HTTP y dominio municipal, comprueba los
contenedores esperados y rechaza fuentes vacías o ambiguas. Escribe JSONL de forma
atómica después de analizar ambas fuentes. La actualización vuelve a leer ambos
inventarios íntegros, sin watermark de fechas que pudiera perder documentos.
Cada documento incluye `source_url` de su página contenedora; el registro conserva
la URL del instrumento y el texto descriptivo PGOU de la fuente.

Pruebas ejecutadas, **7 correctas**:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_barcena_de_cicero -v
```

Cubren agrupación/deduplicación, aislamiento documental y exclusión de formularios,
semántica de fechas, descubrimiento y ambigüedad del enlace PGOU, rechazo de cambios
y paginación, actualización completa, conservación del resultado anterior ante un
error y configuración del manifest. Los fixtures son HTML estructural reducido;
la ejecución real es independiente de esos fixtures.

Reproducción de la extracción directa, sin publicación ni base de datos:

```python
from pathlib import Path
from municipio.adapters.barcena_de_cicero import BarcenaDeCiceroAyuntamientoAdapter
adapter = BarcenaDeCiceroAyuntamientoAdapter(
    'barcena-de-cicero', config={'evidence_dir': str(Path('evidence').resolve())})
result = adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))
```

Resultado en vivo: **2 registros y 10 documentos**. Evidencia local sin incorporar
al código: `evidence/proyectos.jsonl`, `evidence/validation.json`, capturas HTML
`home.html`, `urbanismo.html`, `pgou.html` y diez `document-XX.prefix`.
`validation.json` registra `live_records`, `source_urls`, limitaciones, hora UTC
y comprobaciones de los documentos. Los diez enlaces respondieron HTTP 200;
se leyó únicamente un prefijo de 512 bytes por archivo, verificando `%PDF-` en los
seis PDF y `PK` en los cuatro ZIP, con tipos MIME correspondientes. El servidor
respondió 200 a las peticiones Range, por lo que se cerraron los streams tras
el prefijo. Esta comprobación acredita respuesta y formato, no integridad completa
de los archivos ni contenido de sus páginas/miembros internos.
