# Villamartín — Cádiz — INE 11041

Investigación y extracción real: 7 de noviembre de 2026. Runtime usado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Fuentes oficiales y alcance

La web del Ayuntamiento, https://www.villamartin.es/, enlaza la sede
https://villamartin.sedelectronica.es y su portal de transparencia. El inventario
actual de «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» está en
https://villamartin.sedelectronica.es/transparency/d58cdc0b-39ed-4a07-a79b-a047ac45c7b5/.
Anuncia 132 documentos distribuidos en planeamiento (72), planes ambientales
(1), normativa (3), obras e infraestructuras (3), indicadores (1), calificaciones
ambientales (47) y proyectos de actuación (5). No se equiparan calificaciones,
formularios o anuncios de contratación con licencias concedidas.

El adaptador cubre exclusivamente **7.1 Planeamiento urbanístico**:
https://villamartin.sedelectronica.es/transparency/b02afb40-7954-4692-b8c1-431b2fd2da28/.
Es una cobertura parcial del municipio, completa para las entradas y documentos
anunciados en ese apartado durante la ejecución. No cubre los otros apartados,
el tablón, toda la contratación o todo el archivo histórico de obras.

Resultado real: **3 instrumentos y 72 documentos únicos**:

- Modificación del Plan Parcial Sector Sau 4 Prado del Guadalete: 1 documento,
  https://villamartin.sedelectronica.es/preview-document/1006c73c-f6f9-437d-afdd-6e9a0dc78da6.
- Modificación Plan Especial La Estación: 8 documentos, incluidos documento
  ambiental, documento urbanístico y anuncios de aprobación provisional,
  https://villamartin.sedelectronica.es/transparency/61be2cbc-8e48-49e5-bdf6-cea57cf710b0/.
- Plan General de Ordenación Urbanística de Villamartín: 63 documentos,
  https://villamartin.sedelectronica.es/transparency/d9a10fff-da06-4dbe-b090-eaff84a0a0f9/.
  Incluye anuncios, memorias fragmentadas, normas, 46 planos y documentación
  ambiental/económica, con títulos que indican versiones provisionales.

Cada carpeta de instrumento genera un registro; sus subcarpetas no son nuevos
proyectos. Se conservan los títulos y enlaces de cada documento y la ruta de
carpetas oficial. El documento directo del plan parcial es un instrumento
identificado por su nombre, sin inventar un número de expediente.

## Navegación y paginación

La sede usa Apache Wicket: las carpetas se abren mediante acciones GET públicas
del HTML que redirigen a URLs estables de transparencia. No se ejecuta JavaScript.
«Mostrar más» devuelve XML con componentes HTML incrementales: se procesan hasta
que desaparece el botón. La carpeta de 46 planos requirió la página inicial y
cuatro respuestas adicionales (10 + 10 + 10 + 10 + 6). No se impone un límite de
páginas que pueda truncar resultados. Se rechazan páginas sin tabla, enlaces de
otro host, controles de paginación desconocidos y páginas sin progreso. Cada
carpeta comprueba su total documental anunciado, también de forma recursiva.
Una diferencia provoca error antes de reemplazar el JSONL anterior.

Los enlaces persistentes son `preview-document/<uuid>`. Una comprobación real del
documento Prado del Guadalete obtuvo ficha HTTP 200, metadatos de documento PDF y
un visor cuyo recurso devolvió firma `%PDF-`. Se capturó solo el primer bloque del
PDF; no se descargaron o interpretaron todos los PDFs. Las URLs temporales del
visor o de navegación no se usan como identidad del instrumento.

## Fechas, estado y geometría

No se emiten fechas genéricas, de publicación o de acuerdo: el listado no las
ofrece con semántica verificable. Las fechas en nombres de documentos se conservan
como texto. La fecha de creación electrónica de una ficha tampoco acredita una
aprobación o publicación. No se infieren fases actuales de los anuncios antiguos.

Como contraste, el Ayuntamiento mantiene una comunicación específica del PGOU:
https://www.villamartin.es/actualidad/noticias/231-aprobacion-provisional-2-de-plan-general-de-ordenacion-urbanistica-pgou.
Remite al BOJA de 30/12/2020 y describe un acuerdo de 11/04/2019 y actuaciones
posteriores. Esa comunicación confirma que el inventario incluye etapas históricas;
no se usa para atribuir una fecha única al conjunto de versiones. La resolución
oficial se puede consultar en https://www.juntadeandalucia.es/boja/2020/250/52.
El scraper no pretende extraer todos los instrumentos del BOJA ni certificar vigencia.

No hay coordenadas verificadas: `geometry_status: unavailable` y
`publication_ready: false`. El manifiesto fija `schedule.enabled: false`,
`geocode.jitter_missing: false` y `licencias.enabled: false`. Las actualizaciones
vuelven a leer el inventario completo; no simulan un cursor incremental. La política
compartida clasifica las tres entradas como pendientes de identidad suficiente;
no se falsifican referencias administrativas para eludir esa clasificación.

## Validación y evidencia local

Comando de pruebas:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_villamartin -v`.
Ocho pruebas correctas: identidad municipal, carpetas/recuentos, XML incremental,
agrupación, ausencia de fechas inferidas, fallo por cobertura incompleta sin perder
salida previa, repetición de páginas, rechazo de formularios/contratación/noticias
y licencias desactivadas.

Extracción real mediante `load_manifest(Path('data/municipios/villamartin/manifest.yaml'))`,
`load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`,
con `capture_dir` local configurado solo para esa ejecución. Evidencia sin commit:
`evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/parser-tests.txt`,
`evidence/live/source-*.html`, capturas de investigación y muestra parcial PDF.
La validación contiene recuentos reales, URLs consultadas, limitaciones, comprobación
PDF y referencias a las capturas. Sin ejecución programada, geocodificación ni publicación.
