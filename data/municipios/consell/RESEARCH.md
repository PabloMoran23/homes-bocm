# Consell (07016), Illes Balears

Revisión y extracción real: 2026-11-09. Adaptador único del inventario municipal de planeamiento; no es un censo de obras ejecutadas ni de licencias concedidas.

## Contrato y configuración

Se inspeccionaron primero `municipio/manifest.py`, `municipio/adapters/portal.py`, el registro dinámico y los ejemplos Manlleu, Hernani y Chipiona. Se respeta el contrato de cuatro métodos del adaptador; actualización = sustitución atómica de una instantánea completa. No se modifica código compartido ni dependencias. El manifiesto identifica Consell, Illes Balears, INE `07016`, y desactiva licencias, ejecución programada y jitter de coordenadas.

## Fuentes oficiales descubiertas

La portada [municipal](https://ajconsell.net/ca) y el menú de [Urbanisme](https://ajconsell.net/ca/urbanisme) permiten descubrir cinco instrumentos. La página Urbanisme contiene principalmente los datos de contacto; el inventario real está en su submenú. Se extraen exclusivamente los enlaces de esa sección, sin confundir navegación general, noticias, formularios o contratación con proyectos.

| Instrumento y página oficial | Documentos distintos enlazados | Páginas recorridas |
| --- | ---: | ---: |
| [Adaptació de les NNSS de Consell al Pla Territorial de Mallorca](https://ajconsell.net/ca/arxius-i-documents/adaptacio-de-les-nnss-de-consell-al-pla-territorial-de-mallorca) | 84 | 101 |
| [Modificació puntual de les NNSS](https://ajconsell.net/ca/modificacio-puntual-de-les-nnss) | 1 | 1 |
| [Catàleg de Protecció del Patrimoni Històric](https://ajconsell.net/ca/arxius-i-documents/cataleg-de-proteccio-del-patrimoni-historic-del-municipi-de-consell) | 13 | 8 |
| [Normes Subsidiàries](https://ajconsell.net/ca/normes-subsidiaries) | 1 | 1 |
| [Modificació puntual NNSS: aparcament dissuasiu](https://ajconsell.net/ca/modificacio-puntual-nnss-consell-aparcament-dissuasiu) | 16 | 3 |

Resultado: cinco registros, 115 enlaces a documentos y una referencia externa legada. Se consultaron 115 páginas HTML únicas incluyendo el índice Urbanisme. Los documentos pertenecientes a cada instrumento se agrupan, deduplicando por URL y reteniendo las páginas de procedencia. Las NNSS publicadas por separado se conservan como recurso municipal distinto de su adaptación al PTM: no se afirma que sean versiones jurídicas independientes o simultáneamente vigentes.

La adaptación contiene Avanç, aprovació inicial y aprovació provisional, además de carpetas anidadas. La carpeta de aprobación inicial tiene paginación Drupal (`?page=1`, con vuelta a `?page=0`); se recorren todos los enlaces numerados y siguientes, deduplicando URLs visitadas. No hay límite de resultados que recorte registros; el límite defensivo de 400 páginas por instrumento provoca error, nunca una salida parcial.

El aparcamiento enlaza su [inventario técnico](https://ajconsell.net/ca/arxius-i-documents/modificacio-puntual-nnss-consell-aparcament-dissuasiu) y desde él un paquete de 15 documentos; se agrupa con el edicto, sin generar 16 proyectos. El catálogo incluye planos, memoria, normas de protección y edictos. El alias `www.ajconsell.net` del catálogo sirvió la portada durante la investigación; el dominio canónico `ajconsell.net` sí expone el catálogo y sus documentos. El adaptador normaliza ambos alias.

## Fechas y significado

La fecha que el portal muestra junto a un archivo se guarda como `documentos[].fecha_portal`, con su significado explícito: fecha mostrada/carga del archivo, no fecha de aprobación ni publicación BOIB. Las fechas jurídicas estructuradas (`fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob`) y la fecha genérica permanecen nulas. No se determina una fase actual a partir del nombre de una carpeta histórica.

Comprobación documental manual: el [edicto del aparcamiento](https://ajconsell.net/sites/cilma_consell/files/2025-01/Edicte%20BOIB%20aprovaci%C3%B3%20inicial%20NNSS%20de%20Consell%20aparcament%20dissuasiu.pdf) identifica la aprobación inicial por el Pleno de 26/11/2024, publicación en BOIB núm. 11 de 23/01/2025 y firma de 21/01/2025. El portal muestra 29/01/2025 para el archivo. Esta distinción se comprobó en el PDF capturado (`evidence/document-4.pdf` y su texto), pero el parser HTML no automatiza lectura de PDFs ni copia esos valores como constantes. El PDF de las NNSS contiene disposiciones de planeamiento, no concesiones de licencias. El PDF de la modificación genérica no produjo texto con `pdftotext`; no se inventa un ámbito o fecha adicional.

## Cobertura y limitaciones

- Inventario de documentos actualmente accesibles en Urbanisme, con materiales históricos; no se afirma exhaustividad sobre todo el planeamiento o actuaciones municipales. No se recorren todos los anuncios BOIB, sede electrónica, plenos, noticias o contratos. No se ha verificado un registro público de licencias concedidas y no se extraen solicitudes.
- Tres carpetas publicadas vacías: [Cartografia](https://ajconsell.net/ca/arxius-i-documents/cartografia), [Documents](https://ajconsell.net/ca/arxius-i-documents/documents), [ISA](https://ajconsell.net/ca/arxius-i-documents/isa). Quedan registradas como limitaciones; se recorren igualmente los documentos de las carpetas superiores y restantes subcarpetas.
- La [referencia municipal Medi ambient](https://ajconsell.net/ca/enlla%C3%A7os/memambiental/medi-ambient) apunta literalmente a `http://libre/www.ajconsell.net/Aprovacio_provisional_NNSS/Memoria_ambiental.pdf`. Se retiene en `referencias`, con estado no verificado, sin resolver ese host ni contarlo como documento descargable. No se reescribe inventando una URL válida.
- Los enlaces documentales proceden del inventario oficial. Se descargó y comprobó la cabecera PDF de una muestra por cada uno de los cinco instrumentos; no se garantiza la accesibilidad o integridad de los 115 archivos. Las capturas HTML conservan su procedencia completa.
- No hay geometrías de proyecto verificadas: latitud, longitud y geometría nulas; `publication_ready=false`. No se geocodifican centroides ni se aplican desplazamientos.
- No se fabrican números de expediente para satisfacer la política compartida. El registro dinámico clasifica los cinco instrumentos como `pendiente / insufficient_identity_evidence`; son instrumentos reales del inventario, pero no actividad validada para publicar. Esa clasificación y el resultado de extracción se guardan en la evidencia local.
- Un cambio de estructura, fallo de descarga de una página o detalle sin documentos produce error antes de reemplazar el archivo de salida. Si la ruta legada del catálogo vuelve a servir la portada, se informa expresamente de la omisión.

## Validación reproducible

Runtime preinstalado utilizado:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_consell -v
```

Nueve pruebas offline: identidad del manifiesto e importación dinámica, descubrimiento y deduplicación, procedencia y fechas, paquete relacionado, rechazo de portada/formularios/enlaces ajenos, referencia legada, agrupación con segunda página, preservación de la salida ante fallo de paginación y licencias desactivadas.

Extracción real a través del registro de adaptadores (incluye la anotación de política compartida):

```python
from pathlib import Path
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter
manifest = load_manifest('consell')
manifest.portal.config['capture_dir'] = 'evidence'
load_portal_adapter(manifest).backfill_proyectos(Path('evidence/proyectos.jsonl'))
```

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/proyectos.entities.json`, HTML con nombre hash y PDFs de muestra. `validation.json` relaciona las URLs consultadas, hashes y capturas, conteos, limitaciones y verificaciones de muestras. No se ejecutó publicación, sincronización, despliegue ni acceso a credenciales.
