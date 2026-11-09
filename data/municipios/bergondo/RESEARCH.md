# Bergondo — INE 15008, A Coruña, Galicia

Verificado el 2026-11-09 con el runtime preinstalado. Se revisaron primero
`municipio/adapters/portal.py`, el cargador/esquema de `municipio/manifest.py`,
el registro de adaptadores y los ejemplos Hernani y Chipiona. No se modifican
fuentes compartidas ni dependencias.

## Descubrimiento y alcance

La página oficial https://bergondo.gal/areas-e-servizos/urbanismo/ enlaza las
cuatro colecciones municipales implementadas. El acceso con `www.bergondo.gal`
y User-Agent `Mozilla/5.0` redirige al dominio canónico y respondió HTTP 200.
El primer intento sin ese User-Agent al dominio canónico devolvió 403; un
User-Agent ampliado sufrió una desconexión. El adaptador usa el acceso que se
verificó en vivo, con timeout de 40 segundos y errores explícitos.

Inventarios recorridos íntegramente, sin paginación observada:

- https://bergondo.gal/areas-e-servizos/urbanismo/borrador-do-plan-xeral-de-ordenacion-municipal-pxom/
  — un borrador de PXOM, con 25 enlaces a DIE, memorias, catálogo, atlas y hojas
  gráficas. Las parroquias/hojas son documentos del mismo instrumento.
- https://bergondo.gal/areas-e-servizos/urbanismo/modificacion-puntual-das-nnss/
  — tres modificaciones: sexta (precisión de condiciones), séptima (corrección
  de errores) y octava (núcleo de Gandarío). Respectivamente 4, 4 y 6 enlaces
  distintos; la repetición del mismo PDF DOG se deduplica dentro del expediente.
  La publicación común del BOP se conserva en ambos instrumentos pertinentes.
- https://bergondo.gal/areas-e-servizos/urbanismo/plans-especiais/
  — Plan especial de infraestructuras y dotaciones, senda fluvial del Río Maior,
  expediente 2019/U035/000002, con un enlace al ZIP del documento íntegro.
- https://bergondo.gal/areas-e-servizos/urbanismo/proxectos-de-urbanizacion/
  — rotonda Santa Marta de Babío, aprobación inicial, cuatro documentos
  (expediente, proyecto técnico, plano de servicios y anuncios).

Resultado: **6 instrumentos/proyectos reales, 44 enlaces documentales**. Cada
registro conserva URL de inventario, descripción textual municipal, fase y
proveniencia de cada documento. Los IDs combinan ruta de colección y título;
se excluye el prefijo de fase de las modificaciones para evitar cambiar su ID
al pasar de aprobación inicial a definitiva. Las actualizaciones vuelven a leer
los cuatro inventarios; no usan un corte de fechas ni declaran bajas históricas.

La cobertura es parcial: colecciones documentales hoy accesibles, con contenido
histórico; no es un registro exhaustivo de todas las obras ni del planeamiento.
La sede también publica un inventario «Plans e Programas»:
https://sede.bergondo.gal/sxc/gl/portal_transparencia/Institucional_Organizativa/Planes_y_Programas/Planes_Programas.html
Incluye enlaces a planeamiento autonómico, prevención de incendios, movilidad,
subvenciones y actuación municipal 2026. No se incorpora esa lista heterogénea
como proyectos físicos ni se extraen aquí sus anexos o el tablón de anuncios.
No se usan noticias de licitaciones, formularios ni anuncios de contratación
como si acreditasen obras ejecutadas o licencias concedidas.

## Fechas, fases y documentos

`fecha_acuerdo` procede exclusivamente de frases explícitas del cuerpo municipal:
sexta, orden de 2021-12-22; séptima, orden de 2022-01-19; Río Maior, sesión plenaria
de 2025-10-30. Las fechas DOG, BOP, entrada de documentación y entrada en vigor
permanecen en la descripción, no se confunden con el acuerdo. No se asigna
`fecha_publicacion`: las fechas WordPress reflejan publicación/migración de páginas
que contienen varios expedientes y las rutas de subida no fechan un instrumento.
Tampoco se infiere fecha de aprobación de la rotonda, la octava modificación o
el borrador. Las fases reproducen la página, sin certificar vigencia jurídica
actual ni ejecución material.

Se verificaron tres adjuntos representativos, no todos los enlaces: DIE del PXOM,
HTTP 200 `application/pdf`; ZIP del Río Maior, HTTP 404; expediente de la rotonda
en `bergondo.andaina.net`, HTTP 406. Se retienen las URLs originales publicadas
por el Concello y se documenta su disponibilidad limitada. No se afirma haber
leído los PDFs/ZIP ni se reemplazan por archivos inventados. El cuerpo oficial
identifica inequívocamente los instrumentos aun cuando su descarga falla.

## Geometría y límites operativos

`geometry_status: unavailable`, `publication_ready: false`. Hay cartografía PDF
en el borrador y un enlace municipal a planeamiento Xunta, pero no se ha
verificado una capa vectorial por expediente ni coordenadas georreferenciadas.
No se vectorizan planos, no se asigna un centroide municipal y no hay jitter.
`licencias.enabled`, `schedule.enabled` y `geocode.jitter_missing` son `false`.
Los métodos de licencias escriben cero filas y declaran su deshabilitación.

Se rechazan páginas sin estructura/contenido esperado, instrumentos sin enlaces,
IDs repetidos y paginación detectada (`rel=next`, navegación WordPress o enlaces
siguiente/seguinte). Si aparece paginación se falla antes de escribir, hasta
implementar su recorrido; no se acepta una primera página truncada. La escritura
es atómica y una extracción incompleta no sustituye resultados previos.

## Validación reproducible

Desde la raíz del repositorio:

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_bergondo -v
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python - <<'PY'
from pathlib import Path
from municipio.manifest import load_manifest
from municipio.adapters.registry import load_portal_adapter
manifest = load_manifest('bergondo')
manifest.portal.config['evidence_dir'] = 'evidence'
result = load_portal_adapter(manifest).backfill_proyectos(Path('evidence/proyectos.jsonl'))
print(result)
PY
```

Seis pruebas offline: agrupación/deduplicación documental, fases y fechas,
borrador único, acuerdo frente a presentación de documentos, agrupación de obras,
rechazo de cambios/paginación y contrato de carga/escritura ante fallo.
La extracción real se ejecutó mediante el registro de adaptadores y su anotación
de política de entidades; cinco clasificaciones desconocidas no se convierten
en categorías inventadas.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl` (6 registros),
`evidence/validation.json` (conteo, URLs, limitaciones y resultado de política),
`evidence/document_checks.json` (disponibilidad representativa) y capturas HTML
completas de las cuatro colecciones y las páginas de descubrimiento.
