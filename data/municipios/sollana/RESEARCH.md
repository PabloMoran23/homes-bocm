# Sollana (INE 46233), Valencia

Consulta y extracción real: 2026-11-09. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Se revisaron `municipio/manifest.py`, el contrato `adapters/portal.py`, el registro
y los ejemplos de Manlleu y Hernani antes de implementar este adaptador.

## Fuentes oficiales e inventario observado

- [Sede electrónica municipal](https://sollana.sedelectronica.es/info.0): catálogo
  de procedimientos, tablón y enlace al portal de transparencia. Los trámites de
  licencias son procedimientos reutilizables, no concesiones. No se extraen.
- [Transparencia](https://sollana.sedelectronica.es/transparency), sección
  [7. Urbanismo, obras públicas y medio ambiente](https://sollana.sedelectronica.es/transparency/121e9085-fa17-4f32-aae1-7a894be99d2e/):
  anuncia 37 documentos entre todas sus ramas. No equivalen a 37 proyectos.
- [7.1 Planeamiento](https://sollana.sedelectronica.es/transparency/35df81ac-bada-45b6-a9a6-32b8d1875d89/):
  30 documentos, de los que 28 son la rama 7.1.1 de Normas Subsidiarias.
  Los otros dos (7.1.2) son planes de emergencia y riesgo sísmico, excluidos.
- [7.1.1 Normas Subsidiarias](https://sollana.sedelectronica.es/transparency/ad5bab47-aa91-4d82-bffb-7be13f6effb2/):
  14 planos del instrumento base, 12 documentos de cuatro modificaciones y dos
  documentos de dos planes parciales. Es la cobertura principal implementada.
- [7.3 Normativa urbanística](https://sollana.sedelectronica.es/transparency/c17efa7f-a047-4364-9916-ae297963670e/):
  tres documentos. Se incorpora exclusivamente «7.3.1. Ordenances Normes
  Subsidiàries 1990» al mismo instrumento base. Las ordenanzas de alcantarillado
  y de autorizaciones no se convierten en proyectos ni licencias.
- 7.4 Obras públicas e infraestructuras anuncia **cero** documentos. No se
  interpreta como inexistencia de obras en Sollana.
- 7.2 Medio ambiente, 7.5 Indicadores y 7.6 Órgano ambiental quedan fuera del
  alcance. Noticias y contratación no constituyen el inventario de este scraper.
- La web principal `https://www.sollana.es` y su variante sin `www` cerraron la
  conexión en este entorno. La sede oficial sí permite acceso anónimo.
- Como contraste se consultó el [DOGV 2025/24363](https://dogv.gva.es/datos/2025/07/15/pdf/2025_24363_es.pdf),
  relativo al PMUS. Se conservó la captura de investigación, pero **no** se añade
  como registro ni se extraen de él fechas del instrumento base: el adaptador
  tiene como fuente el inventario municipal descrito, no una lista fija de PDFs.

## Registros reales y agrupación

| Instrumento | Documentos | Página municipal |
|---|---:|---|
| Normes Subsidiàries de Planejament Urbanístic de Sollana | 15 (14 planos + texto normativo) | [7.1.1.1](https://sollana.sedelectronica.es/transparency/8219fce1-23d5-4d47-abec-0f149d851d19/) |
| Modificació núm. 7, Zona Puríssima | 5 | [Instrumento](https://sollana.sedelectronica.es/transparency/3249a76a-c975-4667-a1cd-96b87f7e6403/) |
| Modificació núm.8, Zona Motoret | 3 | [Instrumento](https://sollana.sedelectronica.es/transparency/463d615d-e1a6-4889-b036-79fdd489dcce/) |
| Modificació núm. 9, San Vicent | 3 | [Instrumento](https://sollana.sedelectronica.es/transparency/076376df-b896-4993-b77c-bcd0d3a418ab/) |
| Modificació núm. 10, Zona Clots | 1 | [Instrumento](https://sollana.sedelectronica.es/transparency/060fdde3-3847-4139-a51c-347508af033d/) |
| Pla Parcials Ermita 2 | 1 | [Instrumento](https://sollana.sedelectronica.es/transparency/0dd14fb1-6d4e-4632-a28f-8fdd4e7726ea/) |
| Pla Parcial Industria Olivarons | 1 | [Instrumento](https://sollana.sedelectronica.es/transparency/03a3811b-7655-4e40-a512-559dcbdcd364/) |

Total: **7 instrumentos, 29 documentos**, conservando títulos originales y URLs
públicas `preview-document/<uuid>`. Cada documento conserva la página de inventario
que lo enlaza (`source_url`). Los IDs del scraper se derivan de la URL estable de
la carpeta del instrumento; no son números de expediente administrativos.

## Extracción y límites semánticos

El adaptador descubre las carpetas desde la raíz de transparencia y sigue las
acciones públicas Wicket. La respuesta vacía a una acción de carpeta lleva la URL
canónica en la cabecera `Ajax-Location`; no es un fallo ni una carpeta vacía.
No se ejecuta JavaScript de la fuente: únicamente se reconoce `wicketAjaxGet`.

La lista de planos muestra inicialmente diez entradas. Se procesa **Mostrar más**
y los componentes HTML de su respuesta XML hasta agotarlos. La entrada 13 es a su
vez una carpeta que contiene el plano de protección arquitectónica: también se
recorre. Se contrastan los totales por carpeta, contenedor e inventario (28), y se
rechazan ciclos, duplicados, recuentos discrepantes o cambios de estructura sin
escribir un snapshot parcial. Límites defensivos: 100 páginas de continuación y
10 niveles; excederlos produce error, no truncamiento. El incremental actualiza
el snapshot completo y no utiliza un corte por fecha.

Las listas no proporcionan fecha de publicación, acuerdo ni aprobación. Todas
esas fechas y `fase` son nulas. El reloj de la sede, el año 1990 en un título y
la mera presencia de un plano no establecen una fecha de aprobación ni vigencia
jurídica. No se extraen geometrías de los PDFs ni se asigna el centro municipal:
`lat`, `lon` y `geometry` nulos, `publication_ready=false`.

Cobertura **parcial del municipio**, completa para las ramas expresamente
seleccionadas. No hay histórico exhaustivo, expedientes administrativos, licencias
concedidas ni afirmación de obras iniciadas. El clasificador compartido anota los
siete registros como `pendiente` por falta de referencia administrativa compatible
con sus reglas; no se inventan expedientes para alterar esa clasificación.

## Validación y evidencia local

- `python -m unittest municipio.test_sollana -v`: 11 pruebas offline satisfactorias
  (fixtures sintéticos, sin requerir las capturas locales). Cubren alcance del
  parser, acciones, XML, paginación, duplicados, discrepancias de recuento,
  agrupación, campos desconocidos, manifiesto y preservación ante error.
- Extracción real mediante `load_manifest('sollana')` y `load_portal_adapter`,
  llamando a `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: 7 registros
  y 29 documentos. Se verifican IDs únicos y ausencia de fechas/coordenadas
  inventadas. `evidence/validation.json` contiene fecha de consulta, URLs,
  limitaciones, runtime, resultados y hash del JSONL.
- `evidence/final-captures/`: HTML/XML de todas las peticiones de la extracción.
  `evidence/documents/`: vistas documentales y muestra PDF por instrumento.
  `evidence/document-checks.json`: verificación de las 29 vistas públicas y sus
  iframes PDF. Las URLs permanentes son las vistas; las URLs internas del visor
  pueden variar. No se pretende analizar el contenido completo de todos los PDFs.
- Evidencia local excluida de los archivos fuente a incorporar. No se han cambiado
  fuentes compartidas, dependencias ni configuración Git. Sin publicación,
  despliegue, sincronización, geocodificación ni programación automática.
