# Oliva de la Frontera — investigación y cobertura

Municipio: Oliva de la Frontera, Badajoz, Extremadura. Código INE: **06093**.
Comprobación y extracción en vivo: **2026-11-09**.

## Fuente implementada

Inventario público del Ayuntamiento:
<https://olivafrontera.com/plan-general-municipal/>.
La propia página identifica al Ayuntamiento, su dirección en Oliva de la Frontera
(Badajoz) y el correo municipal. El menú lateral identifica el instrumento como
«PLAN GENERAL MUNICIPAL OLIVA DE LA FRONTERA», versión aprobada inicialmente por
el pleno en sesión ordinaria de **31-7-18**.

El adaptador recorre hasta agotar todos los enlaces del árbol público
`/plan-general-municipal/`, tanto los del contenido como los del menú lateral.
La extracción real ha recorrido **21 páginas** y encontrado **45 URL PDF únicas**.
No se extraen noticias, formularios, contratos ni licencias. Se produce **un
instrumento**, no un proyecto por cada tomo o plano. Los enlaces duplicados se
agrupan conservando todas sus páginas de procedencia en `documentos.source_pages`.
Los planos denominados «planeamiento vigente» son documentos dentro del tomo de
información del PGM; no se convierten en supuestos instrumentos adicionales.
El anexo enlazado como `DIPBA_EEPP_AMPLIACIÓN CEMENTERIO` se conserva como documento
del paquete en el que se publica, sin inventar una obra independiente o su ejecución.

Ejemplos de páginas documentales:

- Memoria informativa: <https://olivafrontera.com/plan-general-municipal/tomo-i-informacion/1-memoria-de-informacion/>
- Normas urbanísticas: <https://olivafrontera.com/plan-general-municipal/tomo-ii-ordenacion/4_normas-urbanisticas/>
- Memoria justificativa y anejos: <https://olivafrontera.com/plan-general-municipal/tomo-ii-ordenacion/5_memoria-justificativa-y-anejos/>
- Catálogo: <https://olivafrontera.com/plan-general-municipal/tomo-iii-cbp/>

Algunos botones del contenido apuntan a antiguas rutas
`/documentacion-concejales/`. Se usa el árbol público equivalente que el propio
menú lateral ofrece. No se accede a áreas privadas. Una petición inicial sin
User-Agent recibió HTTP 403; las peticiones posteriores con el User-Agent del
adaptador respondieron HTTP 200. No se eluden autenticaciones ni se usan credenciales.

## Semántica y límites

`fecha_acuerdo=2018-07-31` y `fase=aprobacion_inicial` se extraen de la identificación
expresa de esta versión en la fuente municipal. No son una fecha de publicación
ni una aprobación definitiva. El adaptador exige esa identificación y no la
sustituye por la fecha de subida de los PDF o por la fecha del rastreo.
No se añaden `fecha_publicacion`, coordenadas, geometrías ni licencias concedidas.

Es un inventario actualmente accesible de una **versión histórica**. No afirma
que el PGM sea el planeamiento vigente. La investigación encontró además fuentes
oficiales regionales de modificaciones posteriores de las NNSS; por ejemplo,
la modificación 26 en el DOE del 26-01-2024:
<https://doe.juntaex.es/otrosFormatos/html.php?anio=2024&doe=190o&xml=2024AC0008>.
Estas publicaciones quedan fuera del adaptador: no se presenta el árbol municipal
como un registro completo de NNSS, sus modificaciones, obras o acuerdos recientes.
Tampoco se transforma la consulta de un anuncio en la concesión de una licencia.

Se conservan todos los enlaces PDF encontrados, pero no se parsea su contenido ni
se comprueba individualmente la descarga de los 45 documentos. La procedencia de
cada enlace es su página HTML municipal capturada. Las fechas y la fase describen
el paquete identificado por el Ayuntamiento, no la fecha particular de cada anexo.

No existe paginación en el árbol observado. El parser rechaza señales de paginación,
consultas inesperadas y nuevos enlaces de contenido fuera del ámbito revisado.
Un límite de seguridad de 200 páginas provoca error, sin escribir resultados
parciales. Los fallos HTTP, cambios en el rótulo de la versión o ausencia de
PDF también abortan la extracción. `update_proyectos` vuelve a recorrer el
inventario completo; no usa una ventana temporal que pudiera perder documentos.

## Validación reproducible

Desde la raíz del repositorio, runtime preinstalado:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_oliva_de_la_frontera -v
```

Cinco pruebas pasan: ámbito del contenido, agrupación y procedencia documental,
fecha del acuerdo y ausencia de fechas inferidas, recorrido completo y repetible,
rechazo de paginación/enlaces inesperados, fallo sin sobrescribir resultados y
carga del manifest con licencias desactivadas.

La ejecución real usó `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `capture_dir=evidence`
como configuración local de la ejecución. No requiere modificar el manifest.
Evidencias locales: `evidence/proyectos.jsonl`, `evidence/validation.json`,
`evidence/page-<sha256(URL)[:12]>.html` y `evidence/discovery.json`.
El informe contiene el número de registros, páginas fuente, documentos y límites.
Las evidencias no forman parte de los cuatro archivos fuente entregables.

Manifest: `schedule.enabled=false`, `geocode.jitter_missing=false` y
`licencias.enabled=false`. Sin dependencias nuevas ni cambios compartidos.
