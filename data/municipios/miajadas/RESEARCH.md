# Miajadas — INE 10121, Cáceres, Extremadura

Verificación: 2026-11-07. Un adaptador, sin cambios compartidos ni dependencias.
Cobertura parcial de planeamiento vigente mediante el inventario oficial de la
Junta de Extremadura, SITEX. No representa un inventario completo de obras,
expedientes urbanísticos o licencias. Programación y geocodificación con jitter
desactivadas; `publication_ready: false` porque no hay geometría verificada.

## Fuentes oficiales descubiertas

- https://miajadas.org/ayuntamiento/urbanismo/ — índice municipal: Plan General
  Municipal, proyectos urbanísticos, catálogo de caminos, cesiones y normas
  subsidiarias derogadas. Visible en el navegador de investigación, pero las
  peticiones directas con requests devolvieron HTTP 403, también para www, HTTP
  y la consulta pública WordPress. No se intentó eludir el bloqueo.
- https://miajadas.org/ayuntamiento/urbanismo/plan-general-municipal-de-miajadas/
  — página municipal del PGM, enlaza el acuerdo de aprobación definitiva en DOE
  y una carpeta documental. HTTP 403 desde el extractor; no es la fuente de los
  registros generados.
- https://miajadas.org/ayuntamiento/urbanismo/proyectos-urbanisticos/ — inventario
  municipal estático visible en el navegador de investigación: reparcelación de
  Plaza de los Naranjos, PLEO Los Naranjos, documentación UA-9 de varios años,
  urbanización de 30 naves del polígono agrícola y vial Calle Degollá. HTTP 403
  desde requests. Estos enlaces no se convierten en registros ni se cuentan como
  cobertura de este adaptador. Las distintas entregas UA-9 tampoco se cuentan
  como proyectos independientes.
- https://sitex.juntaex.es/SITEX/planeamiento?ptofigura=37397 — consulta pública
  oficial regional, HTTP 200. Su selector identifica Miajadas mediante **378**,
  identificador interno SITEX, que no se confunde con el INE **10121**.
- https://sitex.juntaex.es/SITEX/ptofiguras/listadoresultadossigcat — búsqueda
  pública del inventario. El JavaScript de la página utiliza POST con el campo
  `municipioseleccionado=378`; GET con ese parámetro no realiza la selección y
  puede mostrar «No hay ningún planeamiento actualmente». El adaptador reproduce
  exclusivamente esa consulta pública, sin sesión autenticada.

## Cobertura real y semántica

La respuesta POST contiene dos árboles HTML completos, LSOTEX y ANTERIOR A
LSOTEX: **53 identificadores distintos**, **2 vigentes**, **51 no vigentes**.
Solo se extraen los vigentes; los otros 51 se contabilizan como excluidos, sin
presentarlos como planeamiento vigente. El refundido raster es una vista
compuesta, no otro instrumento; no se duplica como registro.

1. https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/37397 — Plan General
   Municipal, referencia PGM, depósito CC/054/2020. Aprobación definitiva:
   **2020-12-21**; depósito: **2020-12-22**; publicación de aprobación definitiva:
   **2021-02-11**. Se conservan **95 URLs documentales únicas**, entre anuncios
   DOE, memorias y planos de información, agrupadas en un único instrumento.
2. https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/40599 — modificación puntual
   nº 1 del PGM, referencia PGM.M-001, sobre alturas de edificaciones e
   instalaciones en varias categorías de suelo no urbanizable. Depósito
   CC/001/2025. Aprobación definitiva: **2024-10-31**; depósito: **2025-01-02**;
   publicación de aprobación definitiva: **2025-01-23**. **6 URLs documentales
   únicas**: tres anuncios DOE y tres memorias/anexos.

Las fechas se extraen de los campos explícitos «Fecha AD», «Fecha de depósito»
y «Fecha de publicación AD»; `fecha` queda nula. La fase reproduce «Vigente»,
no el tipo de instrumento. Se conservan también los trámites, con fecha y texto,
incluida la publicación en sede electrónica de 2025-01-16 de la modificación,
que no sustituye a la publicación en DOE de 2025-01-23. Fechas ausentes quedan
nulas; fechas inválidas causan error. No se derivan fechas del nombre de archivo,
del año del encabezado ni de la extracción.

Cada documento incluye título de enlace o atributo `download`, URL original y
`source_url` del detalle SITEX. Los enlaces HTTP originales del DOE del PGM se
conservan tal como figuran en el registro. Para corroborar accesibilidad se
descargaron sus equivalentes HTTPS:

- https://doe.juntaex.es/pdfs/doe/2021/280o/21AC0001.pdf — HTTP 200, PDF,
  captura `evidence/pgm-doe.pdf`.
- https://doe.juntaex.es/pdfs/doe/2025/150o/25AC0002.pdf — HTTP 200, PDF,
  captura `evidence/modificacion-doe.pdf`.

El adaptador lee metadatos estructurados y enlaces; no interpreta ni valida el
contenido completo de todos los PDF ni afirma que cada documento enlazado esté
accesible. No hay coordenadas o geometrías verificadas: `lat`, `lon`, `geometry`
nulos. No se utiliza el centroide municipal del visor como ubicación de proyectos.
No se extraen noticias, contratos, formularios o solicitudes como licencias.

## Comportamiento y validación reproducible

Cada backfill/update refresca el inventario completo, visita todos los detalles
vigentes y escribe una instantánea JSONL mediante sustitución temporal después de
completar las peticiones y el análisis. No usa filtros temporales o un límite de
registros. La respuesta revisada no tiene paginación: los árboles y documentos
están íntegros en HTML. La aparición de controles de paginación o continuación
provoca error para revisar el recorrido, en vez de aceptar una primera página.
Faltas de árboles, municipio incorrecto, identidad/estado desconocidos, detalles
sin documentos, respuestas HTTP fallidas o superiores a 4 MB provocan error.

Pruebas ejecutadas con el runtime preinstalado:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_miajadas -v
```

**7 pruebas pasaron**: selección/deduplicación de figuras vigentes, agrupación de
documentos, semántica de fechas y fechas ausentes, rechazo de paginación o cambio
de municipio/estructura, identidad, licencias desactivadas, actualización completa
y restricciones del manifest. Fixtures mínimos embebidos, sin dependencia de red.

Extracción real realizada mediante `load_manifest('miajadas')`,
`load_portal_adapter(manifest)` y `backfill_proyectos`, con `capture_dir` local
añadido a la configuración solo durante la verificación. Resultado: **2 registros**,
53 entradas examinadas, 51 excluidas. El guard compartido de categorías se ejecutó
mediante el registry: status ok, categorías unknown 2/2; no se inventó una
categoría más específica. Evidencias locales, no destinadas a commit:

- `evidence/proyectos.jsonl`: registros reales completos.
- `evidence/validation.json`: recuento, URLs, parámetros de búsqueda, limitaciones,
  fechas, documentos por registro, prueba y resultado del guard de categorías.
- `evidence/sitex-inventory.html`, `sitex-37397.html`, `sitex-40599.html`:
  respuestas utilizadas por el adaptador en vivo.
- `evidence/source-checks.json`, `municipal-*.html`, `*-doe.pdf`: comprobaciones
  adicionales de las fuentes oficiales y bloqueos HTTP.

Licencias, schedule y jitter permanecen desactivados. Sin cambios en fuentes
compartidas, dependencias, .git ni operaciones de publicación.
