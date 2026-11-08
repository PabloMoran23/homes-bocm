# Tavernes Blanques — INE 46237, Valencia

Investigación y extracción real: 7 de noviembre de 2026. Se revisaron primero
`municipio/adapters/portal.py`, el cargador de manifests, el registro de adaptadores
y los ejemplos de Chipiona y Hernani. No se modifica ningún componente compartido.

## Fuentes descubiertas y alcance elegido

Fuente de extracción: [registro oficial de planeamiento de la Generalitat Valenciana](https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/4%20VALENCIA/46237%20TAVERNES%20BLANQUES/).
La propia ruta identifica provincia y código INE. Es un inventario oficial de
instrumentos municipales conservado por la administración autonómica, no una web
de contratación ni una relación de licencias. Los registros identifican
`source: registro_planeamiento_gva` y `organismo_fuente: Generalitat Valenciana`.
El manifest usa la ruta de integración municipal `proyectos.source: ayuntamiento`;
esto no cambia la procedencia explícita de los datos.

El índice ofrece dos ramas, `1 P. GENERAL` y `2 P. DIFERIDO`. Se recorren ambas
completas y todos sus subdirectorios documentales. Cada carpeta cuyo nombre
comienza por `46237-` y cuatro cifras identifica un instrumento; acuerdos,
publicaciones, memoria, normativa, planos y certificados permanecen agrupados en
su registro, con título, URL y directorio de procedencia de cada documento.
Los nombres son literales del registro, incluidas abreviaturas. El servidor
anuncia UTF-8 pero algunos nombres contienen bytes Latin-1: se decodifican sin
perder los caracteres y se conservan los escapes originales de las URL.

La ejecución dio **11 registros y 84 enlaces documentales**, tras visitar **48
índices**: plan general `46237-1000`, modificaciones/correcciones `1001`, `1002`,
`1003`, `1004`, `1006`, `1007`, `1100` (calle Cervantes), `1101`, `1103` (usos
terciarios y aparcamientos), y homologación/PRI UE 6A `46237-0010`.
No se convierte cada PDF en un proyecto independiente. Se omiten `Thumbs.db` y
la rama explícita `EXPEDIENTES ANULADOS`, que contiene `46237-1008` (anulado por
sentencia) y `46237-1102` (sin efecto). La exclusión queda en `excluded_urls`.
La ubicación fuera de esa rama no prueba vigencia jurídica actual.

La raíz municipal `https://www.tavernesblanques.es`, su variante sin `www`, HTTP
y `/es/urbanismo` cerraron la conexión en las peticiones de investigación; el
navegador de investigación también obtuvo un error 502 en la raíz. No se usa
contenido de terceros como datos extraídos.

Hay una fuente oficial adicional accesible: [pleno extraordinario del 5 de marzo
de 2026](https://plenos.tavernesblanques.es/es/mopleno/16/2871), HTTP 200, con el
punto `Expte. 1509858A. ACUERDO DE INFORMACIÓN PÚBLICA DEL PLAN GENERAL ESTRUCTURAL
Y DEL PLAN DE ORDENACIÓN PORMENORIZADA...`. Se guarda la captura como contexto.
**Este adaptador no extrae el nuevo PGE/POP en tramitación de 2026**, que no figura
como tal en el inventario seleccionado. Tampoco rastrea todos los plenos o
boletines. Su cobertura es parcial y documental, no un historial completo de
urbanismo ni de obras ejecutadas.

## Semántica y comprobación documental

No hay licencias concedidas en esta extracción. `licencias.enabled`,
`schedule.enabled` y `geocode.jitter_missing` son `false`. No se generan
coordenadas, fechas, fases, importes o estados de aprobación a partir de nombres
de carpeta. Los registros llevan `publication_ready: false` y
`geometry_status: unavailable`.

Se descargó una muestra real: el BOP de la modificación n.º 12, enlazado desde
`46237-1103/01 APROBACIÓN`. Respondió HTTP 200, `application/pdf`, 154444 bytes,
firma `%PDF-`. El texto identifica al Ayuntamiento, el registro autonómico
`46237-1103` y la modificación puntual 12. Distingue el **acuerdo plenario del
27/06/2024**, la **publicación del 24/07/2024** y la **inscripción del 11/07/2024**.
Esas fechas no se incorporan a los registros: el scraper enumera documentos y no
interpreta el texto de los PDF. Las carpetas tituladas APROBACIÓN son procedencia
documental, no una fase inferida. No se verificó individualmente la descarga de
los otros 83 enlaces ni se digitalizó la cartografía.

## Funcionamiento y validación reproducible

El recorrido no tiene un límite de páginas que recorte resultados. Los índices
son listados de directorios sin paginación; ante enlaces de siguiente página,
consultas inesperadas, cambio de estructura, repetición de expediente, directorio
vacío, error HTTP o instrumento sin documentos se produce un error antes de
reemplazar la salida. Se respetan el host y el subárbol municipal. `update` vuelve
a extraer una instantánea completa para reflejar retiradas y anulaciones.

Runtime utilizado, sin instalar dependencias:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_tavernes_blanques -v
```

**8 tests correctos**: agrupación y separación de instrumentos, exclusión de
anulados, recorrido completo, paginación/cambios de estructura, ámbito de enlaces,
documentos ausentes, duplicidad de identidad, codificación, carga del manifest,
licencias desactivadas y sustitución de la instantánea.

Ejecución real mediante `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`; config temporal
`capture_dir: evidence/live-captures`. La anotación compartida identifica los once
registros como expedientes, con cero entidades desconocidas. No se ejecutaron
publicación, geocodificación, bases de datos ni comandos de despliegue.

Evidencia local, fuera de los cuatro archivos fuente: `evidence/proyectos.jsonl`,
`evidence/validation.json` (conteo real, todas las URL visitadas, exclusiones,
limitaciones y comprobación del PDF), `evidence/live-captures/*.html` (respuestas
originales), `evidence/tests.txt`, `evidence/sample-mp12-bop.pdf`, su texto extraído
y `evidence/pleno-2871.html`. Las capturas `inventory-*.html` y `discovery.json`
documentan también la exploración previa, incluida la rama anulada. No se incluye
la evidencia como código fuente ni se realiza commit.
