# Amurrio — INE 01002, Álava, País Vasco

Verificación: 2026-11-07. Adaptador único:
`municipio.adapters.amurrio:AmurrioAyuntamientoAdapter`.

## Fuentes oficiales y alcance

Se revisaron primero el contrato `municipio/adapters/portal.py`, el cargador
`municipio/manifest.py` y los ejemplos Hernani, Manlleu y Chipiona.

Inventarios municipales públicos, ambos HTTP 200 y sin sesión:

- https://udala.amurrio.eus/cas/pgou — documentación del PGOU y apartado
  MODIFICACIONES. Contiene el plan general (47 documentos) y el plan especial
  Parque Fotovoltaico Ekiola (5 documentos).
- https://udala.amurrio.eus/cas/servicios/urbanismo-obras-y-servicios/urbanismo/planes-urbanismo
  — modificación puntual estructural del PGOU (4 documentos). Las ordenanzas
  y el reglamento del consejo asesor se excluyen: no son proyectos independientes.

La navegación municipal de Urbanismo y el enlace municipal «Plan general» permiten
localizar estas páginas. Son inventarios de documentos, no noticias ni anuncios
de contratación. El extractor recorre las listas completas de ambas páginas y
agrupa normas, memoria, planos, participación y anuncio en su instrumento padre.
No interpreta cada PDF como un proyecto, ni mezcla los planos de Ekiola con el PGOU.
Se conservan título y URL de cada documento y su página de procedencia.
Los espacios en las URL se codifican, sin corregir nombres o etiquetas originales.

La página Planes Urbanismo también remite al inventario foral:
https://web.araba.eus/es/urbanismo/planeamiento-urbanistico#amurrio
Ese registro externo no forma parte de la extracción implementada. Tampoco se
pretende cubrir todo el histórico, todo el planeamiento de desarrollo ni todas
las obras públicas. La actualización reemplaza una instantánea completa de estos
dos inventarios; no usa fechas como cursor ni conserva instrumentos retirados.
Los identificadores locales proceden de página y título; no son números oficiales
de expediente, y un cambio de denominación puede cambiar el identificador.

## Fechas, fases y comprobación de documentos

Los HTML no indican las fechas de acuerdo y publicación de cada instrumento.
`fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan en null.
Solo la fase del PGOU se fija como «aprobación definitiva», literalmente indicada
por el enlace de anuncio. No se asigna fase a Ekiola ni a la modificación a partir
de su tipo o de una fecha de archivo.

Como comprobación documental manual se descargaron tres PDF oficiales, guardados
localmente junto con su texto extraído mediante el `pdftotext` preinstalado:

- [Anuncio PGOU](https://udala.amurrio.eus/images/docs/pdf/PGOU_HAPO/Anuncio%20BOTHA%20y%20EAE.pdf):
  BOTHA 12, publicación 2023-01-30; acuerdo plenario de aprobación definitiva
  2022-06-30. Son fechas distintas.
- [Anuncio Ekiola](https://udala.amurrio.eus/images/docs/pdf/PGOU_HAPO/Ekiola/Anuncio_BOTHA_n24_de_26_02_24_cast-eusk.pdf):
  BOTHA 24, publicación 2024-02-26; acuerdo plenario 2023-11-21; inscripción
  registral 2024-02-08, asiento 2024/7. El anuncio identifica expediente
  2022/S04.01.01.06/1. Ninguna de estas fechas se convierte en fecha de licencia.
- [Memoria de modificación](https://udala.amurrio.eus/images/docs/pdf/PGOU_HAPO/modificacion/MEMORIA.pdf):
  modificación del artículo 17 y definición de usos en AC 21 Maskuribai,
  AC 22.1 Aldaiturriaga Centro y AI 23 Maskuribai-Larrinbe. Documento de mayo de
  2025; sello de entrada 2025-05-28. Esa entrada no acredita aprobación.

Estas comprobaciones prueban que hay instrumentos reales, pero no se incrustan
sus fechas como constantes del scraper. El adaptador no descarga ni analiza PDF
en ejecución. Los demás enlaces se retienen como inventario documental, sin
prometer disponibilidad de todos los ficheros.

## Exclusiones y geometría

https://udala.amurrio.eus/cas/servicios/urbanismo-obras-y-servicios/urbanismo/licencias-y-consultas-urbanisticas
contiene información sobre licencias y consultas, no un registro comprobado de
concesiones. Los formularios y la descripción del procedimiento no generan filas.
`licencias.enabled: false`; ambos métodos de licencias generan un fichero vacío.

`geometry_status: unavailable`. Las fuentes ofrecen planos PDF; no se ha
verificado una capa vectorial enlazada a estos instrumentos. No se digitalizan
planos ni se añaden centroides o coordenadas. `lat`, `lon`, `geometry`: null;
`publication_ready: false`. No se afirma que no exista cartografía externa.
`schedule.enabled: false`, `geocode.jitter_missing: false`.

## Reproducibilidad y evidencia local

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Pruebas: `python -m unittest municipio.test_amurrio -v` — 5 pruebas aprobadas.
Cubren agrupación, deduplicación de documentos, estabilidad de ID ante cambios de
PDF, exclusión de formularios/ordenanzas, fechas desconocidas, paginación,
estructura ausente, procedencia de enlaces, extracción completa, escritura
atómica ante fallo y licencias deshabilitadas.

Extracción real realizada cargando el manifest con `load_manifest('amurrio')` y
`load_portal_adapter(manifest)`, llamando exclusivamente a `backfill_proyectos`.
Resultado: **3 instrumentos, 56 enlaces documentales**. Evidencia local en
`evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/pgou.html`,
`evidence/planes.html` y los tres PDF/textos descritos arriba. La anotación común
clasifica los tres registros como pendientes de identidad suficiente; los IDs
locales no suplantan referencias de expediente. La revisión independiente sigue
pendiente; la extracción no implica aceptación ni publicación.

No hay paginación activa en los inventarios examinados. Si aparece navegación
siguiente, enlaces de paginación o parámetros de desplazamiento, el parser falla
explícitamente: no trunca en silencio. También falla ante redirecciones,
inventarios ausentes, documentos sin agrupación o cambios de estructura. No
sobrescribe una salida válida si falla cualquiera de las dos fuentes. Un cambio
de diseño o un inventario sin instrumentos requiere revisión.

La evidencia no se incorpora a los cuatro ficheros fuente solicitados. No se
modificaron código compartido, dependencias ni configuración de despliegue.
