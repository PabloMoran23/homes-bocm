# Noblejas — INE 45115, Toledo

Verificación en vivo: 2026-11-09. Adaptador de un solo municipio, cobertura
parcial de instrumentos de planeamiento publicados por el Ayuntamiento. No es
un registro completo de proyectos, obras, expedientes históricos ni licencias
concedidas. Programación desactivada y sin desplazamiento de coordenadas.

## Fuentes oficiales descubiertas

- https://noblejas.es/transparencia/ — HTTP 200. El apartado de urbanismo remite
  al inventario municipal de Urbanismo; también enlaza la sede electrónica.
  Captura local `evidence/transparencia.html`. No se ha investigado un registro
  autenticado ni se afirma cobertura de la sede.
- https://noblejas.es/area-urbanismo/ — HTTP 200. Inventario actual con secciones
  de NNSS, modificaciones puntuales 2, 4 y 5, reparcelación UA-66, ampliación de
  plazo de urbanización del Parque Tecnológico Lineal, bases para selección de
  urbanizador Los Gorriones y UE-1, proyectos industriales/fotovoltaicos y
  formularios/ordenanzas. El enlace «NORMAS SUBSIDIARIAS» conduce al segundo
  inventario. Se extraen únicamente modificaciones y reparcelación UA-66 de esta
  página. Los proyectos privados, PTL y las bases quedan fuera del alcance de
  este adaptador; los impresos y ordenanzas fiscales no se convierten en proyectos.
- https://noblejas.es/ordenacion-municipal/ — HTTP 200. Colección de memoria,
  normas, gestión, planos informativos y planos de ordenación. Se agrupa como un
  único instrumento NNSS, siguiendo la denominación del inventario de Urbanismo,
  sin interpretar el encabezado genérico «Plan de ordenación municipal» como un
  nuevo POM aprobado. Contiene también textos modificados/refundidos: no se
  afirma que todos los documentos correspondan a una única versión vigente.

Ambos inventarios son páginas Elementor completas, sin paginación observada.
El parser recorre todos los documentos del ámbito seleccionado, sin límite de
registros, y falla si detecta controles de paginación. Un futuro diseño paginado
requiere adaptar la navegación antes de reanudar la extracción.

## Registros y agrupación

La ejecución real produjo cinco registros:

| Instrumento | Referencias documentales |
| --- | ---: |
| Normas Subsidiarias — colección municipal | 36 |
| Modificación puntual 2 | 4 |
| Modificación puntual 4 | 1 |
| Modificación puntual 5 | 4 |
| Proyecto de reparcelación UA-66 | 3 |

Los documentos de cada sección mantienen título, URL absoluta y página de
procedencia en `documentos`. Memoria, planos, resolución y anuncios de una misma
sección no generan proyectos separados. El identificador depende del instrumento,
no del orden ni del número de PDFs. Los textos refundidos del inventario general
se conservan dentro de esa colección; no se presentan como nuevos expedientes.
La misma URL puede tener títulos distintos en el inventario (por ejemplo, anexos
y catálogo); ambos rótulos se conservan como referencias de la fuente.

La colección contiene una URL publicada con extensión `.pdff` para el estado de
la propiedad urbana. Se conserva literalmente, sin reparar ni inventar un destino.
No se afirma disponibilidad o validez de todos los PDFs enlazados. Las capturas
HTML son la fuente efectiva del parser; las descargas PDF siguientes se usaron
como comprobación manual de procedencia y alcance, no como una segunda extracción.

## Fechas y estado

- MP4: el rótulo municipal «APROBACION DEFINITIVA CPOTU 22-03-2023» permite
  `fecha_aprob=2023-03-22`, con referencia exacta en `fecha_aprob_fuente`.
  La ruta `/2023/10/` del PDF no se utiliza como fecha de aprobación/publicación.
- MP5: se conserva la fase de información pública indicada en sus documentos,
  sin afirmar aprobación definitiva. El anuncio municipal descargado identifica
  expediente 2025/1018 y resolución de 26-03-2025; el parser de inventarios no
  extrae este expediente/fecha desde el PDF. El título del anuncio DOCM señala
  publicación 02-05-2025; tampoco se convierte en fecha de acuerdo. Captura
  `evidence/mp5notice.pdf` y texto `evidence/mp5notice.txt`.
- UA-66: resolución de información pública y proyecto dividido en dos PDFs,
  reunidos en un registro. El prefijo 13/04/2021 de la sección se mantiene en el
  título sin atribuirle significado de aprobación o acuerdo. La resolución
  descargada es imagen sin texto útil con pdftotext (`evidence/ua66.pdf`).
- MP4: PDF descargado (`evidence/mp4.pdf`); pdftotext tampoco recuperó texto
  útil. La evidencia de fecha del adaptador es el título visible del inventario.
- NNSS y MP2: fechas y fase desconocidas, sin inferencias.

`fecha`, `fecha_publicacion` y `fecha_acuerdo` quedan nulas. Un anuncio de
información pública no se interpreta como licencia concedida. No se extraen
coordenadas ni se sustituyen por centroides; `lat`, `lon`, `geometry` son nulos y
`publication_ready=false` en todos los registros. Los planos PDF enlazados no
constituyen geometría vectorial verificada por esta implementación.

## Validación reproducible

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `-m unittest municipio.test_noblejas -v`: seis pruebas aprobadas (agrupación,
  fechas explícitas, identidad estable, exclusión de formularios/bases/trámites,
  rechazo de navegación o paginación y contrato de adaptador/manifest).
- `NoblejasAyuntamientoAdapter('noblejas', {'capture_dir': 'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`:
  cinco registros reales, 48 referencias, HTTP 200 en ambas fuentes.
- `evidence/validation.json`: recuento `live_records`, URLs de las fuentes y
  limitaciones. HTML de ambas fuentes guardado por el propio adaptador.
- `update_proyectos` refresca el inventario completo; no mantiene un cursor ni
  promete reconstrucción histórica. Una respuesta inesperada o inventario vacío
  provoca error antes de escribir el resultado. Licencias desactivadas.

Solo se añaden manifest, investigación, adaptador y pruebas. Evidencia local no
versionada; sin instalación de dependencias, credenciales, acceso a producción,
publicación ni operaciones remotas de repositorio.
