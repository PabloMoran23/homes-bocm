# Bellreguard — INE 46048, Valencia

Investigación y extracción real: 9 de noviembre de 2026 (UTC). Se revisaron antes el contrato `municipio/adapters/portal.py`, el esquema y cargador `municipio/manifest.py`, el registro de adaptadores y los ejemplos de Chipiona, Hernani y Manlleu. No se modificaron fuentes compartidas ni dependencias.

## Inventario oficial y alcance

Fuente: https://web.bellreguard.net/urbanisme/ — web del Ajuntament de Bellreguard, HTTP 200 en la ejecución real. El bloque «Ordenació urbanística. Plànols i normativa» contiene un acordeón de tres grupos documentales:

* «Nomativa urbanística» → [Normes urbanístiques](https://web.bellreguard.net/wp-content/uploads/2020/02/normas-urbanisticas.pdf).
* «Zona urbanística poble» → [Plànol Zona urbanística poble](https://web.bellreguard.net/wp-content/uploads/2019/10/Ordenacio-poble.pdf).
* «Zona urbanística mar» → [Plànol Zona urbanistica mar](https://web.bellreguard.net/wp-content/uploads/2019/10/Ordenacio-platja.pdf).

El primer PDF identifica literalmente en portada «PLAN GENERAL DE BELLREGUARD» y «AJUNTAMENT DE BELLREGUARD», seguido de las normas urbanísticas. Se comprobó con `pdftotext`, sin agregar dependencias. Los dos planos no ofrecen texto extraíble con esta herramienta: su identificación procede de los rótulos del inventario municipal. Se agrupan las tres piezas del bloque en **un solo registro documental del Plan General**; no son tres proyectos diferentes. Se conserva para cada pieza su título, URL, rol y página de procedencia. El identificador del instrumento es estable aunque cambien las rutas de los documentos.

La página mezcla este inventario con información catastral y noticias de obras (calles, Passeig Joan Miró y conexión ciclista). Estos contenidos quedan fuera del alcance de este adaptador. No se consideran las solicitudes de licencia como concesiones, ni los anuncios de contratación como proyectos. No se ha verificado un inventario público de licencias concedidas.

Cobertura expresamente **parcial**: este bloque municipal, no el historial completo de instrumentos, modificaciones, expedientes ni obras del municipio. No hay paginación en el bloque inspeccionado. El parser procesa todos sus grupos y enlaces, sin límites de número de registros ni cortes silenciosos. Ante paginación detectable, grupos desconocidos o documentos ausentes/cambiados, produce error para exigir revisión; no afirma rastrear otros inventarios o la paginación de noticias.

## Semántica y comprobaciones

La disponibilidad actual de la documentación no prueba su vigencia jurídica, integridad ni aprobación. Las carpetas `/2019/10/` y `/2020/02/` son rutas de alojamiento y **no se convierten en fechas de publicación o acuerdo**. `fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` permanecen nulas; no se asigna fase. No hay geometría verificada ni coordenadas. `publication_ready` es falso. El manifiesto desactiva licencias, programación y jitter geográfico e identifica municipio, provincia e INE.

El adaptador descarga la página y verifica todos los PDF (éxito HTTP, tipo `application/pdf`, firma `%PDF-`) antes de escribir el resultado. Una descarga fallida no sustituye la salida previa. Los incrementales refrescan el bloque completo sin cursor de fechas. El límite de respuesta genera error si se supera; no produce un documento cortado.

Pruebas ejecutadas con el runtime preinstalado:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_bellreguard -v
```

Resultado: cuatro pruebas correctas. Cubren agrupación y procedencia, exclusión de enlaces ajenos, fechas y coordenadas ausentes, cambios de estructura, paginación, URLs no documentales, carga desde manifiesto y conservación de salida ante fallo documental.

Ejecución real mediante `load_manifest('bellreguard')`, `load_portal_adapter(...)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con captura local activada en la configuración de esa ejecución. Resultado: **1 registro, 3 documentos PDF**, con anotación de la política compartida del registro de adaptadores. Esa política clasifica el registro como categoría desconocida (`unknown`); no constituye una validación semántica independiente ni habilita publicación.

Evidencia local, no destinada a commit: `evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/urbanisme.html`, los tres PDF y sus extracciones de texto. La validación registra instante, URLs, número real de registros, tamaños, SHA-256 y limitaciones. No se ejecutaron publicación, base de datos, despliegue ni pasos globales del pipeline.
