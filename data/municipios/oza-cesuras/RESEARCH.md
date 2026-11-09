# Oza-Cesuras — INE 15902, A Coruña

Verificación en vivo: 2026-11-09. Adaptador único de obras públicas reales,
con cobertura parcial municipal, sin licencias concedidas ni publicación automática.

## Descubrimiento e inventarios oficiales

- Directorio provincial: https://dacoruna.gal/direct/directorio-concellos
  identifica el municipio, su web y su sede.
- Web municipal: https://www.concellodeozacesuras.es/web/index.aspx
  HTTP 200; portada de noticias con 70 páginas. No se rastrea este archivo ni se
  presenta su primera página como inventario completo de proyectos.
- Sede: https://ozacesuras.sedelectronica.es/info.0 — HTTP 200. La portada contiene
  formularios de solicitud urbanística y tres publicaciones de documentos del
  mismo Plan especial de dotaciones para edificio de usos múltiples en Borrifáns.
  Es una lista de últimas publicaciones, no un inventario íntegro. No se generan
  tres proyectos a partir de esos documentos, ni se extraen formularios como licencias.
- **Fuente implementada:** https://plan-unico.dacoruna.gal/oza-cesuras/
  HTTP 200, inventario oficial provincial de inversiones del Plan Único POS+.
  La cabecera identifica «PLAN ÚNICO Oza-Cesuras»; el contenido estructurado de
  la página también identifica DIR3 L01159027. Es una fuente de la Deputación,
  no una página del ayuntamiento. El manifest usa el modo existente
  `proyectos.source: ayuntamiento`; los registros declaran `source: diputacion`
  y `organismo_fuente: Deputación da Coruña` para conservar la procedencia efectiva.

## Cobertura y semántica

Extracción completa de la lista actual de **85 obras aprobadas**: 2017 (15),
2018 (12), 2019 (13), 2020 (3), 2021 (9), 2022 (7), 2023 (4), 2024 (8),
2025 (9), 2026 (5). Incluye redes de abastecimiento/saneamiento, pavimentación,
aceras, equipamiento físico y otras inversiones descritas por su denominación
original, sin expandir abreviaturas ni dividir actuaciones compuestas.
Ejemplos: «Conducion abastecemento de Bandoxa a Trasanquelos» (2020) y
«Colector de saneamento en Mangoño. Parroquia de Mandaio. Oza-Cesuras» (2024).

Todas las tarjetas y ejercicios están en el HTML servido, sin peticiones de
paginación. El extractor comprueba el total «Obras aprobadas» contra las tarjetas
extraídas; un desajuste, duplicado ambiguo, cambio de municipio o enlace de
paginación provoca error antes de reemplazar el fichero de salida. No hay límite
artificial de registros ni selección sólo del ejercicio más reciente.

Se conservan presupuesto y aportación en euros como cadenas decimales exactas.
«Aprobada en Plan Único» expresa inclusión en financiación provincial, no licencia,
adjudicación, inicio de obra, ejecución ni terminación. `ejercicio` es un año
presupuestario: **no es fecha de publicación, acuerdo o aprobación**. Estos campos
se dejan nulos porque la fuente no ofrece días concretos.

No hay ID público individual ni referencia de expediente en las tarjetas. El ID
local deriva de ejercicio + denominación y no depende de presupuesto u orden;
un cambio de denominación cambia el ID. Duplicados de esa clave requieren revisión.
Cada tarjeta produce una sola actuación; conserva sus enlaces en `documentos`
sin duplicarlos. En la fuente revisada no hay documentos enlazados en tarjetas:
`documentos: []`. No se añaden PDFs, fechas o expedientes de fuentes no verificadas.
Las fotos y sus pies no se convierten en registros adicionales.

## Geometría y límites de integración

`geometry_status: unavailable`. La fuente revisada no ofrece geometría ni
coordenadas vinculadas a las obras. No se geocodifica al centro municipal ni se
infiere ubicación de los nombres. `lat`, `lon` y `geometry` nulos;
`publication_ready: false`, `geocode.jitter_missing: false`.

El registro compartido carga correctamente el adaptador y su política de entidades
anota las 85 obras como `pendiente / insufficient_identity_evidence`, con informe
`adapter_incident / unknown_entity_spike`: exige referencias oficiales de expediente
u otros identificadores oficiales que esta fuente no publica. Se conserva este
resultado en la evidencia; no se inventa una referencia para eludir el control.
La extracción es usable y verificable, pero su publicación necesita revisión de
identidad y geometría. No se modifica ninguna política compartida.

Cobertura limitada a obras incluidas en este programa provincial. No cubre todo
el planeamiento ni obras financiadas por otras vías ni licencias privadas.
`licencias.enabled: false`; ambos métodos de licencias producen salida vacía
con estado deshabilitado. `schedule.enabled: false`. La actualización vuelve a
leer todos los ejercicios, sin simular un cursor incremental inexistente.

## Validación reproducible

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_oza_cesuras -v` — **4 pruebas OK**.
Comprueban importes, procedencia, fechas nulas, agrupación de documentos,
identidad estable, fuentes incompletas/cambiadas/paginadas, carga del manifest,
métodos de actualización y licencias deshabilitadas.

Se ejecutó `load_portal_adapter(load_manifest('oza-cesuras')).backfill_proyectos`
contra la fuente en vivo, con `capture_dir` local añadido sólo durante validación.
Resultado: **85 registros reales**, ejercicios 2017–2026, sin documentos ni geometría.
Evidencias locales (no se incorporan al código):

- `evidence/proyectos.jsonl`: salida real anotada por la política compartida.
- `evidence/validation.json`: conteo, fuentes, cobertura y limitaciones.
- `evidence/plan-unico.html`: captura de la petición real del adaptador.
- `evidence/municipal.html`, `evidence/sede.html`, `evidence/pos.html`:
  capturas del descubrimiento.
- `evidence/proyectos.entities.json`: resultado del control de entidades.
