# Tossa de Mar — INE 17202, Girona

Verificación en vivo: 2026-11-09, con el runtime preinstalado
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Adaptador único: `municipio.adapters.tossa_de_mar:TossaDeMarAyuntamientoAdapter`.

## Descubrimiento y fuentes oficiales

- [Servicios municipales](https://www.tossademar.cat/ca/serveis), HTTP 200:
  enlaza «Projectes en tràmit» y las herramientas municipales de planeamiento.
- [Projectes en tramitació](https://www.tossademar.cat/ca/schedule/projectes-en-tramitacio-83),
  HTTP 200: enumera siete proyectos/documentos y remite expresamente al epígrafe
  «2. NORMATIVA / 2.1. PROJECTES EN TRAMITACIÓ» de la sede electrónica.
- [Inventario documental de proyectos](https://tossademar.eadministracio.cat/transparency/51471d1c-4688-4527-a683-90c502316644/),
  HTTP 200: fuente de extracción. Tabla `TransparencyListPanel` con siete
  documentos técnicos y dos carpetas de ordenanzas ajenas al alcance. No se
  observaron controles de paginación. Las carpetas de ordenanzas no se recorren.
- [Herramientas urbanísticas municipales](https://www.tossademar.cat/ca/localitzacio),
  HTTP 200: enlaza el [expediente POUM en RPUC](https://dtes.gencat.cat/rpucportal/#/consulta/detallExpedient/224889)
  e Instamaps. Estos enlaces se identificaron; sus contenidos y geometrías no
  se extrajeron ni se atribuyeron a los proyectos del inventario técnico.
- [Planeamiento en el portal AOC](https://seu-e.cat/ca/web/tossademar/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic),
  HTTP 200: deriva a RPUC/MUC para el municipio `17202`, sin inventario propio
  de instrumentos en la respuesta consultada. No se usa como fuente de filas.

## Registros y procedencia

Se extraen seis obras/proyectos, conservando los siete títulos y enlaces
`preview-document/<UUID>` originales en `documentos`, con `source_url` por
cada documento. Se conservan el inventario y un enlace documental principal.

| Obra identificada | Documentación del inventario |
| --- | --- |
| Museo municipal | PROJECTE-MUSEU_Proj_Executiu |
| Llar d'infants | PROJECTE-LLAR_INFANTS_Proj_Basic_i_Executiu |
| Ampliación Túrsia | PROJECTE-TURSIA_Proj_Ampliacio_Basic |
| Biblioteca | PROJECTE-BIBLIOTECA_Proj_Bàsic |
| Recuperación Camí de Ronda Porto Pi | Fase 1 y Fase 2, agrupadas bajo la obra común |
| Pista polideportiva descubierta | Proyecto básico y ejecutivo |

Las siete páginas documentales respondieron HTTP 200 y contenían un iframe
PDF. No se analizan los PDF ni se reutilizan sus enlaces temporales de sesión.
La vista previa del museo muestra «Data de creació 16-oct-2023»: esa fecha es
metadato del documento y no acredita publicación, acuerdo o aprobación.
Todos esos campos quedan nulos. Tampoco se infiere un estado vigente del
rótulo «en tramitació»: se conserva como `contexto_publicacion`, con `fase` nula.

## Cobertura y comportamiento

Cobertura parcial del inventario técnico de primer nivel accesible actualmente;
no es un censo de todas las obras, de todos los instrumentos urbanísticos ni de
licencias concedidas. Se excluyen ordenanzas, formularios, anuncios de
contratación y navegación. Las dos fases del camino de ronda se agrupan sin
perder sus enlaces; las variantes `_Proj_` de una obra también se agrupan.
Identificadores estables derivados del título de la obra normalizado; un cambio
sustancial de título puede cambiar la identidad, pues no hay expediente común
publicado en esta tabla.

El adaptador exige la sección y tabla esperadas, documentos con enlaces
estables en el dominio oficial y al menos una obra. Rechaza respuestas vacías,
redirecciones inesperadas, proyectos en carpetas sin enlace documental y
controles de paginación detectados; ante una futura paginación exige revisar
el recorrido antes de emitir un snapshot, sin truncar silenciosamente. No hay
límite de filas. Petición con timeout de 40 segundos y respuesta limitada a
3 MB que falla si se excede. La actualización vuelve a extraer la tabla entera.

No se verificó un registro público de licencias concedidas: `licencias.enabled`
es falso. No hay coordenadas ni geometría acreditada por esta fuente: `lat`,
`lon` y `geometry` son nulos y `publication_ready` es falso. No se sustituyen
por centros municipales ni por la vista inicial de un mapa. Tanto
`schedule.enabled` como `geocode.jitter_missing` son falsos.

## Validación reproducible y evidencia local

- `.../venv/bin/python -m unittest municipio.test_tossa_de_mar -v`: nueve pruebas
  correctas, cubriendo agrupación, enlaces, exclusiones, fechas y geometría
  desconocidas, paginación, fallos de fuente y actualización completa.
- Llamada real a `TossaDeMarAyuntamientoAdapter(config={'capture_dir': 'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`:
  seis registros y siete documentos.
- `evidence/proyectos.jsonl`: registros reales extraídos por el adaptador.
- `evidence/validation.json`: recuentos, fuentes, limitaciones y comprobación de
  las siete vistas previas; `evidence/live-inventory.html`: respuesta usada.
- `evidence/discovery-*.html`, `evidence/inventory-*.html` y
  `evidence/document-<UUID>.html`: capturas del descubrimiento y la verificación.

La evidencia queda local; los únicos cuatro archivos fuente añadidos son el
manifiesto, esta investigación, el adaptador y sus pruebas. No se requiere
ningún cambio compartido ni de dependencias.
