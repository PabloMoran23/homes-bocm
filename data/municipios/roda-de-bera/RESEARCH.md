# Roda de Berà — fuentes y cobertura

Municipio: **Roda de Berà, Tarragona, Catalunya; INE 43131**. Investigación y
extracción realizadas el 2026-11-08. Se revisaron `municipio/manifest.py`, el
contrato `municipio/adapters/portal.py`, el registro de adaptadores y los ejemplos
de Manlleu y Hernani antes de implementar este adaptador.

## Inventarios oficiales utilizados

- [Obra pública](https://web.rodadebera.cat/territori/urbanisme/obra-publica):
  categoría municipal con 145 artículos, seis páginas (`start=25`, `50`, `75`,
  `100`, `125`, además de la inicial). Expedientes publicados en este inventario
  con identificadores de 2017 a 2026; esto **no** establece las fechas de los actos.
- [Projectes d'urbanització](https://web.rodadebera.cat/territori/urbanisme/gestio-urban/projectes-d-urbanitzacio):
  cuatro artículos, una página: UA 27 (3666/2023), UA 28 Hilovisa (7332/2020),
  y polígonos 1 y 2 de la UA 8-2 (1843/2018 y 1546/2018).

Son inventarios de documentación técnica de actuaciones físicas concretas,
no una búsqueda de noticias o anuncios de contratación. Cada artículo se abre
para conservar los enlaces de su cuerpo a documentos, con título y página de
procedencia. Por ejemplo, la [memoria de alumbrado en Reina Fabiola](https://web.rodadebera.cat/territori/urbanisme/obra-publica/9182-exp-7093-2026-memoria-valorada-de-millora-de-lenllumenat-al-carrer-reina-fabiola-de-roda-de-bera)
enlaza una memoria valorada municipal. Se descargó ese PDF como comprobación
representativa de acceso (HTTP 200 y cabecera `%PDF-`), sin interpretar firmas ni
atribuirle una fecha de aprobación.

Resultado observado: **149 artículos, 146 expedientes, 225 enlaces documentales
con procedencia** (todos PDF alojados en el dominio municipal). El mismo archivo
puede conservarse más de una vez si figura en distintas páginas de procedencia.
Se agrupan los artículos con idéntico número/año de expediente:

- 2648/2024: telelectura y memoria de digitalización del ciclo del agua;
- 5584/2022: dos publicaciones de mantenimiento del carrer Vendrell;
- 10842/2018: dos publicaciones del proyecto de vivienda municipal en Miramar.

Los títulos de todos los artículos se conservan en `fuentes`; los documentos no
se convierten en proyectos independientes. Referencias distintas se mantienen
separadas aunque sus títulos sean semejantes; no hay evidencia para fusionarlas.

## Otras fuentes oficiales descubiertas y límites

- [Planejament urbanístic vigent](https://web.rodadebera.cat/territori/urbanisme/ordenacio-urbana/planejament-vigent)
  remite al RPUC y enlaza documentos de trama urbana, casco antiguo y capacidad
  acústica. No se ha extraído el registro completo del RPUC ni se afirma cobertura
  de todo el planeamiento vigente. Captura local `evidence/planejament.html`.
- [Gestió urbanística / Projectes](https://web.rodadebera.cat/territori/urbanisme/gestio-urban/projectes)
  publica reparcelaciones y bases de compensación; queda fuera de estos dos
  inventarios de obras y urbanización.
- [Portal de transparencia: Urbanisme](https://seu-e.cat/ca/web/rodadebera/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme)
  presenta accesos a planeamiento, licencias y tramitación de proyectos.
  [Tramitació de projectes i memòries](https://seu-e.cat/ca/web/rodadebera/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/tramitacio-de-projectes-i-memories-176)
  contiene documentación histórica de varias de estas actuaciones; no se mezcla
  para evitar duplicaciones y atribuciones de estado entre portales.

No se ha verificado un inventario público de **licencias concedidas**. Los
formularios, trámites, ordenanzas, noticias y enlaces de licitación no se usan
como licencias ni como registros independientes de proyecto. Licencias y
programación quedan desactivadas en el manifiesto.

## Semántica y comportamiento

- Cobertura parcial de dos inventarios municipales, no de toda la actividad
  urbanística ni de todas las obras existentes o ejecutadas.
- `fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` y `fase` son nulos.
  No se deducen del año del expediente, ruta del archivo o palabra «aprovació».
  Los PDF se enlazan, pero su contenido, firma y fechas no se extraen.
- La referencia procede del título visible, no del slug URL: hay discrepancias
  entre ambos. El año incompleto `3714/202` se conserva literalmente, sin
  inventar `2021`. Los ceros iniciales del número se normalizan únicamente para
  agrupar e identificar; `expediente_original` conserva la referencia visible.
- Coordenadas y geometría son nulas; `publication_ready=false` y
  `geocode.jitter_missing=false`. No se usan centroides municipales.
- Se recorren todos los enlaces de paginación del inventario hasta agotar la
  cola. Páginas repetidas, rutas inesperadas, errores HTTP, cambios de estructura,
  artículos sin documentos y límites de seguridad provocan un error antes de
  reemplazar el JSONL. No se guarda un resultado parcial como extracción completa.
- Actualización = refresco completo de estos inventarios, no incremental por
  fechas ni historial de documentos eliminados. No se descarga cada PDF durante
  el scrape: la evidencia de cada enlace es su artículo municipal.

## Validación reproducible

Runtime preinstalado utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas offline:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_roda_de_bera -v
```

Diez pruebas: paginación y rechazo de cambios, páginas repetidas sin sobrescribir
una salida anterior, procedencia documental, fechas nulas, agrupación, año
incompleto, artículos inválidos, carga del manifiesto, licencias desactivadas y
actualización completa.

Extracción real por el manifiesto y registro, sin publicar:

```python
from pathlib import Path
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter
manifest = load_manifest('roda-de-bera')
manifest.portal.config['capture_dir'] = 'evidence/captures'
adapter = load_portal_adapter(manifest)
result = adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))
```

`evidence/validation.json` contiene recuento real, URLs, límites, resultado de
clasificación y hora UTC. `evidence/captures/extraction.json` registra cada URL
consultada, nombre de captura y SHA-256. Se guardan los siete inventarios y los
149 artículos completos, además de un PDF representativo y su comprobación en
`evidence/document-check.json`. Evidencia local, no destinada al commit.
