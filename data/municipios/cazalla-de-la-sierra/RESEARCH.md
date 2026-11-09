# Cazalla de la Sierra — Sevilla — INE 41032

Investigación y ejecución en vivo: 9 de noviembre de 2026.

## Inventarios oficiales y cobertura

La portada municipal https://www.cazalladelasierra.es/ enlaza el apartado [PBOM](https://www.cazalladelasierra.es/pbom/). Este enlaza el [inventario de documentos del PBOM](https://www.cazalladelasierra.es/pbom-documentos/), con paneles de fases 0–3. La extracción conserva todos sus PDF, incluidas memorias, planos, consulta previa, programa de participación, avance y estudios complementarios. Produce **un instrumento**, no un proyecto por plano o anuncio. La página principal dice «Estamos en la FASE 3», conservado literalmente como fase y con URL de procedencia; no se interpreta como aprobación.

El [indicador 50 del portal municipal de transparencia](https://transparencia.cazalladelasierra.es/es/transparencia/indicadores-de-transparencia/indicador/50.-Esta-publicado-el-Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan.-00016/) ofrece las galerías de la **ADAPTACIÓN PARCIAL A LA LOUA DE LAS NNSS MUNICIPALES**. Su memoria y sus planos de información y ordenación se agrupan en **un instrumento**. El título se extrae del encabezamiento de la galería, no del título genérico del indicador.

Resultado real mediante el adaptador cargado por el registro: **2 registros**, con **15 documentos únicos de la adaptación NNSS/LOUA** y **31 documentos únicos del PBOM**. Cada documento conserva URL, inventario de procedencia y referencias con etiqueta/sección. La deduplicación es por URL exacta. El inventario PBOM enlaza el mismo PDF desde «MEDIO FISICO 1» y «MEDIO FISICO 2»; ambas etiquetas se retienen, sin corregir el enlace municipal. El plano i-01 del indicador 50 también aparece duplicado.

Los tres HTML utilizados son páginas completas sin paginación observada. Se leen todos los paneles, incluso los inicialmente ocultos del PBOM, sin límite de registros/documentos. Si aparecen controles de paginación o enlace siguiente, el parser falla expresamente para evitar cobertura truncada. También falla ante cambios de estructura, título no reconocido o ausencia de documentos. Las actualizaciones reconstruyen la instantánea completa; un fallo de extracción conserva la salida previa.

## Fuentes investigadas fuera del alcance implementado

- [Portal de transparencia](https://transparencia.cazalladelasierra.es/es/): enlaza los indicadores municipales y acredita su procedencia.
- [Indicador 53: modificaciones del PGOU](https://transparencia.cazalladelasierra.es/es/transparencia/indicadores-de-transparencia/indicador/53.-Se-publican-y-se-mantienen-publicados-las-modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados.-00016/): contiene «MODIFICACIONES PGOU» y documentos genéricos de planos/fichas/textos, sin identificar individualmente el instrumento. No se inventa una modificación ni se mezcla ese paquete con la adaptación del indicador 50.
- [Indicador 57: proyectos y pliegos de obras](https://transparencia.cazalladelasierra.es/es/transparencia/indicadores-de-transparencia/indicador/57.-Se-publican-los-proyectos-los-pliegos-y-los-criterios-de-licitacion-de-las-obras-publicas.-00016/): muestra procedimientos en plazo/búsqueda; no se transforma contratación en proyectos físicos.
- Las categorías de noticias PBOM/urbanismo no se usan como inventarios. Formularios de licencia y encuestas no son concesiones. No se implementa un registro de licencias.

Cobertura deliberadamente parcial: no es el histórico urbanístico completo, no incluye PEPCH ni todas las modificaciones ni obras públicas. La disponibilidad actual de un documento no prueba vigencia jurídica. La ficha regional de evaluación ambiental del PBOM y los boletines no se incorporan como otro instrumento duplicado.

## Semántica y verificación

Sin fechas de publicación, acuerdo o aprobación: los timestamps del CMS, las carpetas `/2024/02/` y `/2024/11/` y la fase documental no acreditan esas fechas. No se generan coordenadas, geometrías, direcciones ni aprobaciones. Se emiten `publication_ready: false` y `geometry_status: unavailable`. Manifest: licencias y programación desactivadas, sin jitter de geocodificación.

Pruebas ejecutadas con el runtime preinstalado:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_cazalla_de_la_sierra -v
```

**4 pruebas correctas**: agrupación y referencias, ausencia de fechas/geometría inventadas, rechazo de estructura vacía/ajena y paginación, actualización de instantánea, conservación de salida ante fallo, carga por manifest/registro y licencias desactivadas. Las pruebas son autónomas, sin red ni dependencia de evidencia local.

La ejecución real usó `load_manifest('cazalla-de-la-sierra')`, `load_portal_adapter(...)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `adapter.config['capture_dir']='evidence'`. No se ejecutó el pipeline de publicación. Evidencia local no destinada a commit:

- `evidence/proyectos.jsonl`: dos registros reales; anotación de política compartida incluida por el registro.
- `evidence/validation.json`: recuento, URLs, limitaciones, pruebas y muestras documentales.
- `evidence/pgou.html`, `pbom.html`, `pbom-documentos.html`: capturas realizadas por el propio adaptador; `home.html`, `modificaciones.html`, `mods.html`, `obras.html`: investigación.
- Dos archivos `sample-*.pdf.prefix`: primeros 1024 bytes de la memoria justificativa y del resumen ejecutivo PBOM; ambos HTTP 200, `application/pdf`, firma `%PDF-` verificada. Son muestras parciales, no PDF completos ni validación de los 46 documentos.

No hay dependencias nuevas, cambios compartidos, acceso a credenciales, bases de datos ni publicación.
