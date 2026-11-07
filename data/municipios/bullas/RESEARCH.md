# Bullas — INE 30012, Murcia

Investigación y extracción en vivo: 2026-11-07. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales y selección

La página municipal de [Urbanismo](https://bullas.es/areas-municipales/urbanismo/)
publica, dentro de «Licencias urbanísticas / Normativa», el enlace
[APROBACIÓN PROVISIONAL PGMO](https://bit.ly/3eqx4gB). El enlace redirige a la
[carpeta pública del PGMO](https://drive.google.com/drive/folders/1FPot6ymbtwZf_7PWI-NIiPjuYBJkle6O?usp=sharing).
La procedencia municipal se acredita por este enlace; Google Drive aloja los documentos.
No se accede a cuentas ni a credenciales. El host www.bullas.es redirige al dominio sin www.
Una petición inicial sin User-Agent recibió 403; las peticiones del adaptador con User-Agent
recibieron 200. No se usa una copia local como sustituto de la extracción en vivo.

El paquete contiene memoria y anejos, normas, programa de actuación y estudio económico,
planos 2.1–2.7 y catálogo cultural 4.1–4.2. Se extrae **un instrumento real**, agrupando
12 enlaces PDF y dos enlaces de subcarpetas en `documentos`. Cada documento conserva
el título, URL y carpeta de procedencia. No se generan proyectos separados por cada plano.
Se comprobó además la vista pública de Normas: HTTP 200 y título esperado; no se
ha descargado ni analizado el contenido íntegro de los PDF.

También se revisó el [PMUS](https://bullas.es/ayuntamiento-abierto/plan-movilidad-urbana-sostenible/):
la página expone un calendario de elaboración y un acta participativa, además de un documento
externo genérico; queda fuera del adaptador. Los formularios de licencia, legislación,
noticias del área y anuncios de contratación no se convierten en proyectos o concesiones.

## Cobertura y semántica

Cobertura parcial: únicamente el paquete del PGMO actualmente enlazado por Urbanismo,
no todos los instrumentos históricos ni todas las obras públicas de Bullas. La carpeta raíz
contiene cinco entradas, Planos siete y Catálogo dos. El adaptador recorre las subcarpetas
sin cortar resultados: exige que las filas HTML coincidan con `aria-rowcount`, rechaza
paginación explícita y listados de 50 o más entradas por posible carga diferida. Si cambia
el formato o se alcanza el límite de recorrido, falla antes de sustituir la salida.
La página municipal consultada es una página de área, sin paginación del paquete.

Se conserva «APROBACIÓN PROVISIONAL PGMO» como `rotulo_fuente`, sin afirmar vigencia
ni aprobación definitiva. El nombre de la carpeta menciona resolución de alegaciones
08052019 y los archivos ABRIL-2019: no se convierten en fechas de acuerdo o publicación.
Tampoco se usan las fechas de modificación de Drive para esos campos. No se extraen fechas,
fase normalizada ni coordenadas. `publication_ready=false`, `geometry_status=unavailable`.
Licencias, ejecución programada y jitter de geocodificación desactivados en el manifest.

## Validación reproducible

- `python -m unittest municipio.test_bullas -v`: pruebas de selección, semántica sin fechas
  inventadas, rechazo de tablas incompletas/vacías/paginadas, agrupación recursiva y fallo
  antes de sobrescribir resultados; también comprobación del manifest y carga del adaptador.
- Ejecución real de `BullasAyuntamientoAdapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`
  con `config={'capture_dir': 'evidence'}`: 1 registro, 14 enlaces, 3 carpetas recorridas.
- `evidence/validation.json` contiene recuentos, URLs, limitaciones y hashes de capturas.
  `evidence/` es evidencia local, no fuente para el scraper ni contenido para commit.
