# Camarena (Toledo), INE 45031

Investigación y extracción real: 9 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales descubiertas

La [web municipal de Urbanismo](https://www.ayto-camarena.com/areas/urbanismo)
enlaza la sede electrónica y su portal de transparencia. No ofrece un inventario
propio de planeamiento: contiene información catastral y noticias. La noticia del
Silo describe obras físicas, pero no se utiliza para ampliar artificialmente este
inventario de instrumentos. Formularios, anuncios de contratación, convocatorias
de pleno y cortes de suministro no se extraen como proyectos ni licencias.

El [apartado municipal 7 de transparencia](https://camarena.sedelectronica.es/transparency/36778a0d-713b-4a3c-a8ba-f9056d4418d6/)
expone estas carpetas: 7.1 Planeamiento (0), 7.2 Planes medioambientales (0),
7.3 Normativa urbanística (14), 7.4 Obras públicas e infraestructuras (1),
7.5 Indicadores (0). La carpeta 7.4 sólo anuncia un informe de infraestructura
y equipamientos locales de Diputación de febrero de 2017: no se ha convertido
en una obra sintética.

Fuente implementada: [7.3 Normativa urbanística](https://camarena.sedelectronica.es/transparency/bc7f3fd9-4305-42a7-8d98-eeee6b0fd6e8/).
Sus 14 enlaces documentales representan:

- Normas Subsidiarias de 1986: 6 documentos (memorias informativa y justificativa,
  ordenanzas de suelo urbano, normas para suelo urbanizable y no urbanizable,
  plano de clasificación).
- Modificación de 1990: 6 documentos (memoria justificativa, normas urbanísticas,
  ordenanzas urbanas, normas de suelo urbanizable y no urbanizable y plano de
  calificación/clasificación).
- Modificación puntual de Normas Subsidiarias de 1993: 1 documento.
- Modificación puntual de Normas Subsidiarias de 2000: 1 documento.

También se consultó el [portal regional de instrumentos](https://urbanismo.castillalamancha.es/planeamiento/planeamiento-municipal/instrumento-planeamiento-municipal):
la página informativa no expuso un listado municipal en su HTML y advierte de
posibles documentos municipales no depositados. Se prefirió el inventario
municipal directamente disponible. No se emplean resultados de búsqueda como
registros ni se confunde Camarena con Camarena de la Sierra (Teruel).

## Extracción y semántica

El adaptador realiza una sesión HTTP pública sin autenticación. Lee el contador
de 7.3 en la carpeta matriz y la primera página (10 documentos), sigue el callback
Wicket de «Mostrar más» y aplica únicamente los componentes HTML de la respuesta
XML (4 documentos adicionales). No ejecuta JavaScript remoto. Continúa mientras
exista el control; falta de progreso, cambio de estructura, año sin clasificación,
límite de seguridad o discrepancia con el contador producen error antes de
escribir la salida. No hay truncamiento silencioso.

Se emiten **4 instrumentos**, conservando los **14 títulos y enlaces persistentes
`preview-document/UUID`** en `documentos`. Los enlaces de sesión de Wicket no se
usan como identificadores. Los documentos de cada año se agrupan porque sus
rótulos describen las mismas Normas Subsidiarias/modificación; no se emite una
actuación independiente por cada plano o capítulo. Los cuatro grupos conocidos
se validan explícitamente; futuras etiquetas desconocidas requieren revisión.

Los años son etiquetas documentales (`anio_documental`), no fechas de acuerdo,
publicación o aprobación. Las fechas permanecen nulas. La ficha de la memoria
informativa de 1986 muestra «Fecha de creación 12-dic-2017 12:52:14»: es metadato
del documento electrónico, no una aprobación de 1986 ni fecha de publicación
verificada. Su vista previa expone PDF; la comprobación local descargó únicamente
los primeros 4096 bytes y confirmó firma `%PDF-`. No se han analizado los PDF
completos ni verificado su vigencia. La procedencia de cada documento se conserva.

Cobertura parcial: snapshot completo de la carpeta 7.3 disponible hoy, no todo el
histórico urbanístico ni todas las obras municipales. Sin geometrías ni coordenadas
verificadas, `publication_ready: false`. No se ha acreditado un registro de licencias
concedidas. `licencias.enabled`, `schedule.enabled` y `geocode.jitter_missing` son
`false`. Las actualizaciones repiten el snapshot completo; no modifican estado
incremental ni realizan publicación.

## Validación reproducible

`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_camarena -v`

Cuatro pruebas correctas: agrupación/documentos y fechas nulas, paginación XML y
control de integridad del total antes de escribir, rechazo de formularios/vacíos/
etiquetas desconocidas, carga del manifest y licencias desactivadas.

Extracción real mediante `load_manifest('camarena')`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, incluyendo la anotación
compartida de entidades. Resultado: **4 registros y 14 documentos**. Evidencia local
no destinada a commit: `evidence/proyectos.jsonl`, `evidence/validation.json`,
`evidence/captures/source-00.txt` (carpeta matriz), `source-01.txt` (primera página),
`source-02.txt` (paginación XML), ficha documental, prefijo PDF y comprobación HTTP.
No se ejecutó ningún paso de base de datos, geocodificación, sincronización o despliegue.
