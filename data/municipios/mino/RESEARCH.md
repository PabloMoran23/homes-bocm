# Miño — INE 15048, A Coruña, Galicia

Verificado el 2026-11-09 mediante HTTP real, usando el entorno preinstalado.

## Descubrimiento y elección de fuente

- Web municipal: https://www.concellodemino.gal/gl (HTTP 200). Enlaza el
  Xeoportal de Datos municipal:
  https://experience.arcgis.com/experience/958be2eeb0f9421f861a6778feabc825.
- La sede municipal, sección Planes y Programas:
  https://sede.concellodemino.gal/sxc/es/portal_transparencia/Institucional_Organizativa/Planes_y_Programas/Planes_Programas.html
  (HTTP 200), enlaza «Plan general de ordenación munipal (PGOM)» al antiguo
  dominio de planeamiento de la Xunta, con `idconcello=15048`.
  La ruta actual https://siotuga.xunta.gal/siotuga/inventario?inv=1&idconcello=15048
  responde HTTP 200, pero su HTML inicial contiene el buscador, no expedientes.
  No se extraen instrumentos de ese buscador ni se convierten enlaces de menú
  en registros. Tampoco se extrae el plan económico financiero de la sede.
- Fuente seleccionada: https://plan-unico.dacoruna.gal/mino/ (HTTP 200),
  inventario oficial «PLAN ÚNICO Miño», de la Deputación Provincial da Coruña.
  El pie identifica y enlaza https://www.dacoruna.gal. Es un inventario específico
  del municipio, de obras físicas financiadas por POS+, con título, ejercicio,
  presupuesto y aportación. No es un listado de licitaciones ni de noticias.
  Descubierto buscando inventarios oficiales de obras de Miño.

## Extracción y semántica

Una fila de la tabla «Lista de obras e investimentos» representa una obra.
Se extraen **18 obras reales**, ejercicios presentes 2017, 2018, 2019, 2021,
2022, 2024 y 2025. Ejemplos: pavimentación da Rúa Real e cruce da estrada da
praia (2025), parque infantil de Bemantes (2024), instalación colector xeral
alcantarillado na Prata (2021). Se preservan títulos abreviados tal como aparecen.

La página ofrece ejercicios 2017–2026 y selecciona «Todos». Los ejercicios sin
filas no se rellenan. La tabla completa del HTML contiene las mismas 18 obras
que indica «Obras aprobadas». Las tarjetas y fotografías duplicadas no producen
registros adicionales. No hay paginación actual; el parser exige «Todos», esquema
conocido y coincidencia entre contador y número de filas. Rechaza enlaces de
paginación reconocidos, duplicados ambiguos, tabla vacía y cambios de esquema,
en vez de devolver un resultado truncado o aparentemente válido.

`ejercicio` es el año de financiación. No es una fecha de publicación, acuerdo,
aprobación o ejecución: `fecha`, `fecha_publicacion`, `fecha_acuerdo` y
`fecha_aprob` quedan null. «Obras aprobadas» se conserva en `estado_fuente`, sin
inferir concesiones de licencias, adjudicaciones ni terminación de obras.
Importes decimales en euros se conservan como strings exactos. El ID sintético
usa INE, ejercicio y título; no se presenta como número oficial de expediente.
Cambios de importe conservan el ID; cambios de título pueden alterarlo.

Cada registro retiene la URL del inventario y organismo/tabla de procedencia.
Las filas actuales no contienen documentos técnicos enlazados: `documentos=[]`.
Si aparecen enlaces dentro de una fila, se agrupan en esa obra, reteniendo sus
URLs y procedencia; no se generan obras por documento. El catálogo no expone
identificadores oficiales de cada actuación. La política compartida de elegibilidad
puede mantenerlas pendientes por esa carencia; no se fabrican referencias para
superarla. `publication_ready=false`.

El manifest usa `proyectos.source: ayuntamiento` como ruta del contrato local;
la fuente efectiva se identifica explícitamente como `source: diputacion` en las
filas. Backfill e incremental refrescan la instantánea completa; no se interpreta
una ausencia como baja administrativa. El estado incremental no se utiliza.

## Cobertura y geometría

Cobertura parcial, limitada al inventario POS+ publicado. No incluye todas las
obras municipales, planeamiento SIOTUGA, obras privadas ni histórico de licencias.
No se ha verificado registro de licencias concedidas. Los métodos de licencias
producen vacío y estado disabled. Formularios y anuncios de contratación quedan
fuera de la fuente seleccionada.

La tabla no proporciona coordenadas, geometría, CRS ni vínculo con una entidad
vectorial. Se ha identificado el enlace municipal al visor ArcGIS, pero no se ha
verificado una capa enlazable a estas obras. `lat`, `lon` y `geometry` quedan null,
`geometry_status=unavailable`. No se geocodifican títulos ni se aplican centroides.

## Validación y evidencia local

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `python -m unittest municipio.test_mino -v`: 3 pruebas pasan. Cubren importes,
  precisión temporal, identidad estable frente a cambios de presupuesto, múltiples
  filas, agrupación de documentos y rechazo de municipio incorrecto, filtrado,
  paginación, contador incompleto, esquema roto, formularios y duplicados.
- Ejecución real de `MinoAyuntamientoAdapter.backfill_proyectos`, con manifest
  cargado por `load_manifest('mino')`: 18 registros, sin fixtures ni fallback.
- `evidence/proyectos.jsonl`: resultado real; `evidence/validation.json`: contador,
  URLs, limitaciones, fecha de extracción y hash SHA-256 de la captura utilizada.
- Capturas: `evidence/pos-live.html` (ejecución del adapter), `pos.html`,
  `planes.html`, `inventario.html`, `municipal.html` (descubrimiento).

Evidencias locales no destinadas a commit. Solo se añaden los cuatro archivos
fuente solicitados. Sin dependencias ni código compartido modificados.
`schedule.enabled=false`, `geocode.jitter_missing=false`, `licencias.enabled=false`.
