# Borriol — INE 12031, Castellón

Investigación y extracción real: 9 de noviembre de 2026. Un único adaptador,
con cobertura parcial explícita del expediente de urbanización l'Abeller.

## Fuentes oficiales descubiertas

- Ayuntamiento, [Proyectos de urbanización](https://www.borriol.es/es/proyectos-de-urbanizacion/).
  El contenido identifica expresamente un proyecto elaborado para la urbanización
  l’Abeller y enlaza su expediente documental. La relación genérica de servicios
  urbanísticos de esa página no se convierte en actuaciones independientes.
- [Expediente documental l'Abeller](https://borriol.sedelectronica.es/transparency/823ff776-5ccb-4876-a22d-156749324698/).
  La ruta visible del portal lo titula «PROGRAMA DE ACTUACIÓN INTEGRADA L'ABELLER».
  Contiene ocho fichas públicas: memoria, anejos, planos, pliego, presupuesto,
  estudio de seguridad y salud, certificado y edicto de información pública.
  Constituyen **un registro**, conservando los ocho enlaces `preview-document`,
  las etiquetas y los títulos descriptivos originales. No se guardan como enlaces
  permanentes los tokens transitorios de previsualización PDF.
- Ayuntamiento, [Normas subsidiarias y PGOU](https://www.borriol.es/es/normes-subsidiarias-y-pgou/),
  enlaza el [inventario de planeamiento](https://borriol.sedelectronica.es/transparency/8860929b-5322-4ae1-bb74-445cb29abfa1/).
  Se observaron carpetas de texto consolidado diciembre 2023 (121 entradas),
  normas subsidiarias vigentes (82), modificaciones puntuales (93), 2016 (0),
  2018 (4) y catálogo de protecciones (87). Las carpetas usan navegación dinámica
  Wicket. **No se extraen esas carpetas**, ni se presentan como documentos completos
  o proyectos adicionales; esos conteos son entradas documentales, no actuaciones.
- La página municipal de procedimientos administrativos contiene formularios y
  solicitudes. No acredita concesiones y queda excluida.

## Alcance y semántica

El scraper descubre el enlace de sede desde el contenido de la web municipal en
cada ejecución; lee el título de la ruta del expediente y todos sus documentos.
No devuelve un registro precargado ni usa noticias o contratación como proyectos.
La cobertura se limita al expediente enlazado, sin afirmar inventario completo
municipal, vigencia del instrumento, aprobación definitiva o ejecución de obras.

No se observó paginación en las dos páginas extraídas. El parser detiene la
extracción ante controles de paginación, más de un expediente enlazado, carpetas,
entradas documentales incompatibles, pérdida de memoria técnica o cambio de
identidad. Así evita aceptar silenciosamente una cobertura incompleta dentro
del expediente. Las actualizaciones releen el expediente completo.

El título descriptivo del certificado menciona un acuerdo de Junta de Gobierno
Local de 07/11/2019; se conserva literalmente como metadato documental, sin
interpretar su contenido como aprobación definitiva. La ficha del certificado
muestra fecha de creación 11-jun-2020, que no es fecha de publicación ni acuerdo.
No se rellenan `fecha`, `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob`, fase
ni coordenadas. El año 2019 del nombre tampoco se transforma en fecha.
`publication_ready: false` y `geometry_status: unavailable` expresan los límites.
Licencias, programación y jitter están desactivados en el manifest.

## Verificación reproducible

Runtime empleado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_borriol -v`: **4 correctas**. Cubren
agrupación, procedencia, identidad, ausencia de fechas/geometría inventadas,
rechazo de páginas vacías o cambiadas y paginación, y carga mediante el manifest
con transporte simulado.

Extracción real mediante `load_portal_adapter(load_manifest('borriol'))` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con
`adapter.config['capture_dir'] = 'evidence'`: **1 registro y 8 documentos**.
`evidence/validation.json` contiene conteo, fuentes, límites y comprobación PDF.
Las capturas `municipal-projects.html` y `abeller-dossier.html` proceden de esa
misma ejecución. Las capturas discovery documentan también la exploración del
planeamiento excluido. La memoria tiene ficha HTTP 200 y su recurso binario,
consultado con la misma sesión pública y Referer, devuelve HTTP 200,
`application/pdf` y firma `%PDF-`; se guardaron solo los primeros 8192 bytes en
`memory-pdf-prefix.bin`. Una solicitud sin mantener esa sesión devolvió 403;
no se elude autenticación. No se descargó o interpretó el conjunto de PDF.

Evidencias locales, sin publicación, base de datos ni geocodificación. Solo los
cuatro archivos fuente solicitados forman parte de la implementación.
