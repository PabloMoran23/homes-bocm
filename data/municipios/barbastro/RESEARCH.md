# Barbastro — INE 22048, Huesca (Aragón)

Verificación en vivo: 2026-11-07. Adaptador único:
`municipio.adapters.barbastro:BarbastroAyuntamientoAdapter`.

## Fuentes oficiales y alcance

Se inspeccionaron el contrato `municipio/adapters/portal.py`, el cargador y esquema
`municipio/manifest.py`, el registro y los ejemplos Manlleu, Chipiona y Hernani.

La navegación municipal de Urbanismo publica estos inventarios/secciones:

- [Estudios de Detalle](https://barbastro.org/areas/urbanismo/estudios-en-detalle):
  fuente implementada. Índice completo observado de **13 páginas** de instrumentos,
  todas recorridas, con memoria y planos adjuntos. No es una lista de noticias.
- [Planeamiento de Desarrollo](https://barbastro.org/areas/urbanismo/planeamiento-de-desarrollo):
  página explicativa, sin instrumentos enlazados en el cuerpo examinado.
- [Plan General de Ordenación Urbana](https://barbastro.org/areas/urbanismo/plan-general-de-ordenacion-urbana):
  presenta el PGOU y un plano de zonificación. No incluido en este adaptador.
- [Instancias](https://barbastro.org/?Itemid=140): el buscador muestra solicitudes y
  autoliquidaciones urbanísticas; no acreditan licencias concedidas y se excluyen.
- [Sede electrónica](https://barbastro.sedipualba.es/): descubierta en búsqueda;
  no se ha verificado ni implementado un inventario público de concesiones.

La cobertura municipal es **parcial**, limitada al inventario actual publicado de
Estudios de Detalle. «Actual» describe el índice consultado, no la vigencia jurídica
de cada instrumento. No incluye todo el PGOU, histórico, obras públicas, contratación
ni noticias. No afirma concesiones, ejecución material ni viviendas construidas.

## Identidad y documentos

Un registro por artículo municipal, ID estable `barbastro-ed-<id Joomla>`; los IDs
actuales son 1333–1345, descubiertos desde el índice, sin lista fija en el código.
Las dos páginas del Área 19 permanecen separadas: Terrero/Castillo/Beato Ceferino y
Tallada/Castillo/Barranco. El Área 93-A reúne el refundido de E.D. y reparcelación
publicados juntos, sin multiplicarlos por cada PDF.

La descripción se conserva literalmente desde el cuerpo del artículo, también en
modificaciones y textos refundidos. Hay **58 grupos por nombre de archivo**, con
**116 enlaces**: Joomla `/attachments/article/…` y JTAttach `/images/jtattach/…`
coexisten. Ambos se retienen bajo el instrumento y se agrupan por etiqueta visible;
no se ha demostrado que las dos variantes sean idénticas byte a byte. El duplicado
de botón «Descargar» no genera otro documento. Cada grupo conserva la URL de la
página de procedencia. La memoria del Área 09 se descargó como muestra y se
comprobó HTTP 200 y cabecera `%PDF-`; está capturada en evidencia local.

## Fechas, geometría y controles

No se extraen fechas del contenido PDF. Los cuerpos HTML examinados no declaran
fechas de acuerdo/aprobación. `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob`
y `fase` quedan en null: ni las marcas temporales en rutas JTAttach ni una fecha de
subida acreditan aprobación. No se infiere vigencia del hecho de estar en el índice.
Los planos PDF no son geometría georreferenciada verificada: `lat`, `lon` y
`geometry` quedan null, `geometry_status=unavailable`, `publication_ready=false`.

No hay paginación activa observada. El parser rechaza controles de paginación,
contenido vacío, entradas desconocidas o detalles sin instrumento/documentos. Si
aparece paginación requiere implementar su recorrido; nunca acepta una primera
página truncada. No se reemplaza el JSONL hasta haber leído todos los detalles.
El incremental vuelve a obtener una instantánea completa; no mantiene un cursor
que pueda ocultar cambios. Licencias devuelve vacío con estado deshabilitado.

La ejecución a través del registro compartido añade `_entity_policy`: los 13
registros quedan `pendiente`, `insufficient_identity_evidence`, y el informe señala
`adapter_incident` por acumulación de pendientes. El clasificador requiere una
referencia de expediente que no se ha verificado aquí. No se inventa una referencia
ni se modifica la política compartida para hacerlos elegibles: `activity_eligible`
es false. Es una limitación de integración pendiente de revisión independiente,
aunque las páginas y sus instrumentos/documentos sí son extraíbles.

## Validación reproducible

Runtime usado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_barbastro -v
```

Cuatro pruebas pasan: identidad/separación de instrumentos y documentos, fechas
nulas/procedencia, rechazo de contenido/paginación, fallo sin reemplazo parcial,
y manifiesto/licencias deshabilitadas. Fixtures HTML sintéticos dentro del test;
no dependen de los archivos de evidencia ni de la red.

Extracción real realizada con `load_manifest('barbastro')`, configuración local
`capture_dir='evidence'`, `load_portal_adapter(manifest)` y
`adapter.backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
Resultado: **13 registros**. `evidence/validation.json` contiene conteo, URLs,
limitaciones e informe del adaptador; las capturas HTML incluyen índice y los 13
detalles, además de las otras secciones investigadas y la muestra PDF. Evidencia
local excluida de los cuatro archivos fuente entregados.

`schedule.enabled=false`, `geocode.jitter_missing=false`, `licencias.enabled=false`.
Sin cambios compartidos ni dependencias, ni publicación/despliegue.
