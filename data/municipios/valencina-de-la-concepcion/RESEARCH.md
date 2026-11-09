# Valencina de la Concepción — INE 41096, Sevilla

Investigación y extracción real: 8 de noviembre de 2026. Provincia correcta:
Sevilla; «Valencina de la Concepción (Sevilla)» en el encargo identifica el
municipio y no constituye el nombre de la provincia.

## Fuentes oficiales y alcance

- [Portal municipal del PGOM](https://www.valencinadelaconcepcion.es/es/pgom/):
  explica la elaboración del nuevo plan y enlaza su documentación. Su texto
  histórico de consulta previa no se interpreta como estado actual del plan.
- [Inventario documental actual](https://www.valencinadelaconcepcion.es/es/pgom/documentacion/index.html):
  fuente utilizada por el adaptador. HTTP 200, siete bloques documentales y
  26 enlaces PDF, todos servidos en la misma página, sin controles de paginación
  observados. FASE I contiene programación y participación; FASE II, diagnóstico;
  FASE III, memoria de avance, impacto en salud, resumen ejecutivo, planos de
  información y ordenación, y memoria y planos del documento inicial estratégico.
  Se genera **un único instrumento PGOM con 26 documentos**, conservando título,
  URL, sección y procedencia de cada documento. Los planos y anexos no son obras
  o proyectos independientes. No hay lista precargada de expedientes.
- [Urbanismo](https://www.valencinadelaconcepcion.es/es/urbanismo/): página de
  noticias, excluida de la extracción. No se transforma su contenido general en
  proyectos sintéticos ni se incluyen anuncios de contratación.
- [Trámites](https://valencinadelaconcepcion.es/es/ayuntamiento/impresos/):
  formularios de solicitudes y declaraciones, no concesiones verificadas.
- [Fase actual](https://www.valencinadelaconcepcion.es/es/pgom/fase-actual/):
  no proporcionó un estado textual suficiente para inferir una fase legal.
- [Archivo de adaptación de NNSS de Diputación](https://3web.dipusevilla.es/planeamiento/adaptacion_loua/Valencina_96Adapt_P_NNSSPM/96Adapt_LOUA.html)
  y [publicación de normativa de NNSS en BOJA](https://www.juntadeandalucia.es/boja/2021/232/30):
  fuentes históricas localizadas en la búsqueda, fuera de este inventario PGOM.
  No se declara cobertura del planeamiento histórico ni del conjunto de obras.

El refresco vuelve a leer todos los bloques y todos sus enlaces. No existe
límite de registros ni recorte por fecha. Si aparecen controles de paginación,
falta la identidad municipal, desaparece la memoria de avance o cambia la
estructura documental esperada, el adaptador falla en vez de emitir un inventario
parcial como completo. Los documentos repetidos se agrupan por URL conservando
sus secciones. La estabilidad del identificador se basa en el instrumento, no
en una URL individual de PDF.

## Semántica y limitaciones

Cobertura parcial: documentación del nuevo PGOM, no censo de proyectos, obras,
licencias ni instrumentos históricos del municipio. Secciones «FASE III» y
«AVANCE» son etiquetas del inventario; no prueban aprobación inicial o definitiva,
vigencia, ejecución ni concesión de licencia. No se asigna `fase` legal.

`fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` son nulas. Fechas de leyes,
de las NNSS anteriores, de firmas o incluidas en nombres de fichero no se usan
como fecha del PGOM. No se confunde una publicación con un acuerdo. El adaptador
no analiza el contenido PDF para obtener fechas o geometría. Las coordenadas y
geometría son nulas, `geometry_status: unavailable`, `publication_ready: false`.
Licencias, programación automática y jitter están desactivados en el manifest.

## Validación reproducible y evidencia local

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_valencina_de_la_concepcion -v`

Resultado: cinco tests correctos. Comprueban agrupación y enlaces, secciones de
documentos duplicados, rechazo de paginación, ausencia de datos inventados,
rechazo de formularios/identidades y destinos ajenos, y refresco del adaptador.

Se cargó el manifest con `load_manifest` y el adaptador con
`load_portal_adapter`; se ejecutó `backfill_proyectos(Path('evidence/proyectos.jsonl'))`
con `portal.config.capture_dir = 'evidence'` solo para esta ejecución. Resultado:
un registro real, 26 documentos y anotación de política de entidades correcta.
La política clasificó la entidad como `unknown`; no se fuerza una categoría.

`evidence/validation.json` conserva recuentos, URLs, limitaciones, resultado del
adaptador, hora UTC y comprobación de PDF. `documentacion-live.html` captura el
HTML usado en esa extracción; los otros HTML capturan el reconocimiento del
portal. La memoria de avance respondió HTTP 200 y `application/pdf`, con firma
`%PDF-`; `sample-avance-prefix.bin` conserva únicamente sus primeros 1024 bytes.
No se descargaron ni verificaron íntegramente los 26 PDF. La evidencia es local
y queda fuera de los cuatro archivos fuente entregables.
