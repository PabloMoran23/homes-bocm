# Orkoien — Navarra — INE 31906

Verificación en vivo: 2026-11-09. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Descubrimiento y fuentes oficiales

La portada municipal https://www.orkoien.com/ enlaza directamente el inventario
«Fondos Europeos PRTR»: https://www.orkoien.com/fondos-europeos-prtr/ (HTTP 200).
Su sección «Proyectos Ayuntamiento de Orkoien» declara que contiene los proyectos
presentados por el Ayuntamiento al Plan de Recuperación. En la consulta actual
contiene carteles de modernización digital y una ficha textual de obra física:
**RENOVACIÓN DE ALUMBRADO PÚBLICO EN ORKOIEN – III FASE**.
No se utiliza una noticia individual como semilla ni una convocatoria de contratación.

Documento descubierto siguiendo el enlace de esa ficha (HTTP 200, PDF real):
https://www.orkoien.com/wp-content/uploads/2026/01/Comunicacion-web-DUS5000.pdf

La lectura local con `pdftotext -layout` confirma una actuación concreta: el texto
explica la sustitución de luminarias por tecnología LED y la financiación DUS5000.
No es un formulario, solicitud de licencia ni anuncio de licitación. El PDF es una
comunicación municipal de la actuación, no una resolución de concesión de licencia.
El extractor descubre y verifica el PDF, conserva su URL y hash, pero no interpreta
su texto automáticamente. Por ello no exporta importes, ahorros ni estado de ejecución
basados en esta lectura manual.

También se revisaron las páginas municipales de Gestión Municipal, Gobierno Abierto,
Ciudadanía y el Tablón de anuncios:

- https://www.orkoien.com/gestion-municipal/
- https://www.orkoien.com/gobierno-abierto/
- https://www.orkoien.com/ciudadania-2/
- https://www.orkoien.com/tablon-de-anuncios/

Las primeras contienen organización, información general y trámites. El tablón mezcla
noticias y convocatorias y tiene paginación (8 páginas visibles); **no se incorpora ni
se afirma haber recorrido su archivo**. El menú municipal enlaza además la sede y
transparencia en https://orkoien.sedelectronica.es/transparency; no se han validado
allí expedientes individuales ni un registro público de licencias concedidas.
Los PDFs antiguos encontrados en buscadores, sin un inventario actual verificado,
no se convierten en instrumentos vigentes. Las noticias de prensa sobre vivienda
no se utilizan como registros.

## Cobertura y semántica

Resultado vivo: **1 proyecto**, con **1 PDF enlazado**, agrupado como una actuación.
El alcance es parcial: obras físicas de alumbrado con enlaces textuales dentro del
inventario PRTR. Los carteles de modernización digital son imágenes sin ficha textual
y quedan fuera de este alcance; tampoco se realiza OCR de carteles.
No se pretende cubrir todo el planeamiento, inversiones, histórico de obras o licencias.

El identificador se deriva del título normalizado de la actuación, no de cada archivo.
Enlaces repetidos se deduplican y documentos con el mismo título de actuación se
agrupan. Se retiene la página inventario como procedencia y cada URL documental.
No hay fecha explícita de publicación, acuerdo o aprobación en la ficha: se exportan
nulas y no se interpretan las carpetas WordPress `/2026/01/` como fechas de actos.
Tampoco se inventa un número de expediente. La fase queda nula.

No se ha obtenido geometría de la obra ni correspondencia con una capa oficial;
`lat`, `lon` y `geometry` quedan nulos, `geometry_status=unavailable` y
`publication_ready=false`. Sin coordenadas del centro municipal ni desplazamientos.
La anotación compartida de entidades deja este registro como `pendiente`, por falta
de referencia administrativa reconocida por esa política. Se conserva ese resultado,
sin inventar un expediente ni cambiar las reglas compartidas.

## Comportamiento y comprobación

Se recorre toda la sección PRTR entre su encabezado y el siguiente encabezado.
Actualmente no tiene paginación. Si aparece continuación/paginación, una estructura
incompatible, un nuevo enlace de proyecto no revisado, un documento externo o una
respuesta que no sea PDF, se falla explícitamente. No hay límites de filas ni cortes
por fecha; el límite de tamaño de descarga produce error, nunca truncamiento.
Las actualizaciones refrescan la sección completa y la salida se reemplaza únicamente
tras descargar y verificar todos sus documentos. No hay caché de registros prefijados.

Cuatro pruebas `unittest` verifican agrupación y deduplicación, fechas y geometría
nulas, ámbito de la sección, rechazo de paginación/estructura cambiada/enlaces ajenos,
fallo de red sin sobrescribir salida anterior, licencias vacías y contrato del manifest.

Comando de pruebas:

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_orkoien -v
```

La extracción real se ejecutó mediante `load_manifest('orkoien')`,
`load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`,
con `capture_dir='evidence/captures'` en la configuración local de ejecución.
`evidence/validation.json` contiene el recuento vivo, URLs, hashes, capturas,
limitaciones y anotación de la política compartida. Hay HTML de descubrimiento,
PDF original y texto de comprobación en `evidence/`. La evidencia es local, excluida
de los cuatro ficheros fuente entregables.

El manifest desactiva programación, licencias y jitter de geocodificación.
No se han modificado fuentes compartidas ni dependencias, ni ejecutado publicación,
bases de datos, despliegue o sincronización.
