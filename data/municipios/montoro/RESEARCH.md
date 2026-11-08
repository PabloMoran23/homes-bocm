# Montoro, Córdoba — INE 14043

Investigación y extracción en vivo: 2026-11-08. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

## Inventarios oficiales descubiertos

La portada municipal enlaza [Urbanismo](https://montoro.es/urbanismo/).
Esta sección combina botones documentales y un archivo de noticias paginado.
Se recorrieron las tres páginas disponibles:

- https://montoro.es/urbanismo/
- https://montoro.es/urbanismo/page/2/
- https://montoro.es/urbanismo/page/3/

Los botones se repiten entre páginas. El adapter agrupa sus enlaces por instrumento,
conservando las páginas de procedencia. Sigue todos los enlaces de paginación del
archivo; si cambia su ruta, se repite una página o se supera el límite de seguridad,
falla sin escribir un resultado parcial. La última página no ofrece otra página
pendiente. No se cuentan noticias de obras como proyectos en esta implementación.

El Ayuntamiento enlaza también dos archivos públicos de Google Drive:

- [Planeamiento Montoro](https://drive.google.com/drive/folders/1sQco-9ud5FNir8mUjfvRhlWU1S-Tu395?usp=sharing).
  Se comprobó su listado público, con carpetas de NNSS, innovaciones, planes
  parciales, estudios de detalle y PEPCH. Tiene entradas aparentemente duplicadas
  (por ejemplo, las numeradas 36/41 y 39/44). **No se extrae ese archivo**: no se
  verificaron exhaustivamente sus subcarpetas, documentos ni paginación. La captura
  de descubrimiento se conserva localmente como `evidence/discovery-2.html`.
- [PGOU](https://drive.google.com/drive/folders/0B6jMMSrnFaJgaUpoQm1sWi1lRU0?resourcekey=0-aoHFZ6LpOmoNMzAJViI73g&usp=sharing).
  Enlace observado en la sección municipal; contenido no inspeccionado ni extraído.

El portal de transparencia responde con resultados desiguales (403 en algunas
peticiones). La API WordPress de páginas devolvió la misma primera página al
variar `page` y `per_page`; no se usa como inventario ni se supone completa.
Con User-Agent explícito, la sección HTML y sus tres páginas fueron accesibles.

## Cobertura implementada: dos planes municipales documentados

1. **Plan de Acción de Agenda Urbana**. Documento enlazado directamente mediante
   botón en Urbanismo:
   https://montoro.es/wp-content/uploads/2024/09/PLAN-DE-ACCION-AGENDA-URBANA.pdf
2. **Plan Municipal de Vivienda y Suelo de Montoro**. Ficha municipal:
   https://montoro.es/plan-municipal-de-vivienda-y-suelo-de-montoro/
   Documento:
   https://montoro.es/wp-content/uploads/2023/09/Plan-Municipal-de-Vivienda-y-Suelo-2023.pdf
   La ficha dice que se publica para participación durante la redacción, antes de
   proceder a su aprobación. Su metadato `article:published_time` establece
   **2023-09-15 como publicación de la ficha**, no como acuerdo ni aprobación.

El alcance es una selección explícita de estos dos tipos de plan, no el catálogo
completo del planeamiento municipal ni de las obras. Son instrumentos documentados,
no licencias concedidas ni actuaciones físicas extraídas del interior de los PDF.
No se dividen sus documentos o anexos en proyectos independientes. Los enlaces PDF
se extraen del cuerpo del instrumento, sin incorporar documentos de navegación.
Se excluyen solicitudes, criterios sobre placas solares, anuncios de contratación,
noticias ajenas y los archivos Drive mencionados. La vigencia y aprobación actuales
no se verifican. No se extraen fechas del directorio de subida ni de la modificación
del CMS. No hay fechas de acuerdo, aprobación, fases o coordenadas inferidas.
Todos los registros llevan `publication_ready: false` y geometría no disponible.

## Validación reproducible

Pruebas: `python -m unittest municipio.test_montoro -v`, con el runtime indicado:
**6 pruebas correctas**. Comprueban selección, procedencia, agrupación de anexos,
separación entre publicación y aprobación, paginación, rechazo de respuestas
inválidas/repetidas, conservación del resultado anterior ante errores y carga por
manifest/registry con licencias desactivadas.

Extracción real mediante `load_manifest('montoro')`, `load_portal_adapter(manifest)`
y `adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`. Configuración local
`capture_dir=evidence/captures` para guardar HTML de las cuatro peticiones. Resultado:
**2 registros**, tres páginas de inventario y una ficha documental. La actualización
repite esta instantánea completa, sin afirmar incrementalidad ni cobertura histórica.

Se comprobó además cada PDF mediante GET en streaming: HTTP 200, `application/pdf`
y firma `%PDF-` en ambos. Solo se capturó el primer bloque; **no se validó el PDF
completo ni se analizó su texto**. Los prefijos y sus metadatos están en `evidence/`.
La política compartida del registry anotó un registro como documento y otro como
pendiente; ninguno acredita concesión ni es elegible como actividad por esa política.
No se cambia la política para promover estos planes a actuaciones publicables.

Evidencia local: `evidence/proyectos.jsonl`, `evidence/validation.json`, capturas HTML,
resultado de extracción y comprobaciones documentales. No se publica ni se sincroniza.
Manifest: provincia Córdoba, municipio Montoro, INE 14043; `schedule.enabled=false`,
`geocode.jitter_missing=false`, `licencias.enabled=false`.
