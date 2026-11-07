# Zumarraga — INE 20080, Gipuzkoa

Verificación: 2026-11-07. Adaptador específico del inventario documental del nuevo
Plan General de Ordenación Urbana (PGOU). Cobertura parcial: **un instrumento real,
11 documentos PDF únicos en castellano**. No representa todas las obras, el
planeamiento vigente completo ni las licencias de Zumarraga.

## Descubrimiento y procedencia

Se revisaron primero `municipio/adapters/portal.py`, `municipio/manifest.py`, los
manifiestos existentes y los adaptadores de Hernani y Manlleu.

- https://www.zumarraga.eus/eu/ — portada municipal, HTTP 200; enlaza explícitamente
  https://zumarragaplanorokorra.eus/ mediante el banner HAPO. La extracción vuelve
  a verificar este enlace en cada ejecución antes de aceptar el portal externo.
- https://zumarragaplanorokorra.eus/es — inventario del PGOU, HTTP 200, con saludo
  del alcalde, explicación del instrumento y documentación de las diferentes
  etapas. El pie identifica al equipo redactor Territorio y Ciudad SLP; su
  vinculación municipal se acredita con el enlace anterior. El documento conserva
  como procedencia esta página; cada PDF conserva título y URL propios.
- https://www.zumarraga.eus/es/ayuntamiento/normas-subsidiarias — sección oficial,
  HTTP 200, enlaza Udalgeo y GeoZumarraga.
- https://www.udalgeo.com/zumarraga/web/Archivos/Documentos/Documentos.aspx?Idioma=eu
  — HTTP 200, respuesta inicial «Kargatzen... / Direktorioak ez du dokumenturik».
  No se interpreta como prueba de inexistencia de planeamiento ni se extraen
  registros de su interfaz dinámica.
- https://www.geozumarraga.net/es/urbanismo:36/revision-de-las-normas-subsidiarias:m60
  — HTTP 200; catálogo cartográfico de clasificación, delimitaciones, catálogo e
  infraestructuras. No se verificó una geometría vectorial asociable al nuevo
  PGOU mediante identificador de expediente. Sus capas no se convierten en
  instrumentos separados.

Las capturas de descubrimiento son `evidence/home.html`, `discovery-0.html`
(normas en castellano), `discovery-1.html` (euskera), `discovery-3.html` (PGOU en
euskera), `discovery-4.html` (visor), `inventory-0.html` (PGOU castellano),
`inventory-1.html` (Udalgeo) e `inventory-2.html` (GeoZumarraga). Una URL tentativa
`/es/desarrollo-urbano-y-rural` dio 404 (`discovery-2.html`) y queda excluida.
Las capturas `municipal.html` y `pgou.html` corresponden a la ejecución real del
adaptador. Se descartan noticias generales, contratación y formularios: no
acreditan proyectos físicos ni concesiones de licencia.

## Extracción y semántica

Se recorren **todos** los enlaces PDF del inventario castellano, sin cupo de filas
ni documentos, conservando orden, título, URL y página de procedencia. Se exige
identidad de Zumarraga, narrativa del PGOU y memoria, planos y DIE del avance.
Los enlaces repetidos entre las fases y la sección de descargas se deduplican por
URL. Todos pertenecen al mismo PGOU, con ID estable `zumarraga-proy-pgou`:

1. Documento de síntesis.
2. Manual de participación para la ciudadanía.
3. Informe previo.
4. Convocatoria de talleres de participación.
5. Resultado de talleres.
6. Avance: memoria.
7. Avance: planos.
8. Avance: DIE.
9. Síntesis de sugerencias PGOU.
10. Criterios y objetivos PGOU.
11. Documento de alcance PGOU.

El cuestionario de Google Forms no es un documento técnico ni un proyecto; se
excluye. La traducción en euskera está disponible pero no se mezcla ni se convierte
en un segundo instrumento. No hay paginación en el inventario examinado. El
adaptador falla explícitamente si aparecen controles de paginación, si desaparece
el vínculo municipal o si faltan documentos sustantivos, sin sobrescribir una
extracción anterior. Una futura paginación requiere implementar su recorrido
antes de aceptar resultados.

La fase registrada indica elaboración y disponibilidad de documentación de
avance. La descripción de siete etapas es una hoja de ruta, **no evidencia de
aprobación inicial, provisional o definitiva**. No se extraen fechas de las
carpetas `/2024/05/` o `/2025/10/`: son rutas de subida, no fechas de acuerdos o
publicaciones administrativas. `fecha`, `fecha_publicacion`, `fecha_acuerdo` y
`fecha_aprob` quedan nulas. La descripción del registro es un resumen del
adaptador, no una cita literal del portal. No se ha leído el contenido completo de
los PDF para inferir fechas ni decisiones administrativas.

`lat`, `lon` y `geometry` son nulas, `geometry_status: unavailable` y
`publication_ready: false`. Los planos PDF se conservan como documentos sin
inventar coordenadas, centroide, geocodificación ni CRS. Las licencias permanecen
deshabilitadas; ambos métodos producen cero filas y estado `disabled`.
La actualización refresca la instantánea completa del instrumento.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_zumarraga -v`: **5 pasan**. Comprueban
agrupación y deduplicación, procedencia, fechas desconocidas y ausencia de
geometría, rechazo de fuente incorrecta/documentación incompleta y paginación,
escritura por la ruta de actualización y preservación de salida ante fallo de
procedencia, licencias deshabilitadas y carga del manifiesto.

Extracción en vivo: se cargó la clase especificada por el manifiesto y se ejecutó
`backfill_proyectos(Path('evidence/proyectos.jsonl'))` con
`config={'capture_dir': 'evidence'}`. Resultado: **1 registro, 11 PDF**.
Cada URL documental se comprobó adicionalmente mediante GET real: HTTP 200 y
firma inicial `%PDF-`. Son comprobaciones de acceso/formato, no una validación
jurídica del contenido. No se guardaron los PDF completos.

`evidence/validation.json` contiene `live_records`, todas las `source_urls`, fecha
UTC de comprobación, resultados de acceso a documentos y limitaciones. Los HTML
y JSONL son evidencias locales excluidas del commit. Solamente se añaden los
cuatro archivos de fuente solicitados. `schedule.enabled: false`,
`geocode.jitter_missing: false`, `licencias.enabled: false`. Sin publicación ni
acceso a servicios de producción.
