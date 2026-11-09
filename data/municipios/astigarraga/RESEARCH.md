# Astigarraga — investigación y cobertura

Municipio: **Astigarraga, Gipuzkoa, País Vasco; INE 20903**.
Consulta en vivo: **2026-11-08**. Adaptador:
`municipio.adapters.astigarraga:AstigarragaAyuntamientoAdapter`.

Se revisaron primero `municipio/manifest.py`, `municipio/adapters/portal.py`,
`municipio/adapters/registry.py` y los ejemplos de Hernani, Manlleu y Chipiona.
Se respeta el contrato de cuatro métodos y el esquema de manifest; no se
modifican fuentes compartidas ni dependencias.

## Fuentes oficiales descubiertas

La [portada municipal](https://www.astigarraga.eus/es/) enlaza el
[Plan Urbanístico](https://www.astigarraga.eus/es/plan-urbanistico), que ofrece:

- [Planeamiento vigente](https://www.astigarraga.eus/es/plan-vigente): texto
  refundido del PGOU de enero de 2010, con memoria, normas, planos y anexos.
  Sus documentos pertenecen al mismo plan; no son obras independientes.
- [Modificaciones del PGOU](https://www.astigarraga.eus/es/hapo-aldaketak): cinco
  entradas. Se observaron títulos y slugs de enlaces discordantes; no se usa
  este índice para inferir identidades ni aprobaciones.
- [Desarrollo del PGOU](https://www.astigarraga.eus/es/desarrollo-del-pgou):
  **fuente implementada**, cinco fichas con fecha explícita de publicación y
  adjuntos oficiales. No hay controles de paginación en el HTML revisado.
- [Inicio de revisión y participación](https://www.astigarraga.eus/es/haporen-berrikuspenaren-hasiera-eta-herritarren-partehartze-programaren-onarpena):
  contiene el acuerdo de inicio de 22-02-2021; no demuestra aprobación de un
  nuevo PGOU. Fuera del alcance implementado.

También se localizó el [Registro de Planeamiento de Gipuzkoa](https://w390w.gipuzkoa.net/WAS/CORP/DUERegistroPlaneamientoWEB/hasiera)
mediante el buscador; no se integra ni se afirma haber extraído sus expedientes.
La búsqueda web no pudo leer astigarraga.eus por robots, pero las peticiones
HTTP directas al portal municipal devolvieron las páginas públicas con estado 200.

## Registros extraídos

| Instrumento/ficha | Publicación indicada en índice | Adjuntos |
| --- | --- | --- |
| 2ª modificación del proyecto de reparcelación de la UEU 21.1 del área Zarkumendegi del plan general de Astigarraga | 2022-03-29 | 1 |
| Plan especial de ampliación de la Herri eskola | 2021-11-17 | 9 |
| 3ª modificación puntual del Programa de Actuación Urbanizadora (PAU) del área AIU 21 Zarkumendegi del PGOU de Astigarraga | 2021-09-28 | 1 |
| Modificación puntual nº 4 del plan parcial de la AIU 21 Zarkumendegi | 2021-09-28 | 3 |
| Proyecto de Urbanización del Polígono Industrial de Zarkumendegi | 2021-08-02 | 7 |

Cada registro retiene su URL de ficha, la URL del índice y todos sus adjuntos
PDF/ZIP, incluidos títulos, parámetros originales y URL de procedencia. Las
partes documentales de un instrumento se agrupan en `documentos`; no se
confunden con proyectos separados. Compartir el ámbito Zarkumendegi no convierte
sus distintos instrumentos en uno solo. El título se valida contra el de la
ficha, sin interpretar los slugs opacos como identidad o descripción.

`fecha_publicacion` procede exclusivamente de «Fecha de publicación» del índice.
Los parámetros `t=` de adjuntos son versiones/caché, no fechas de aprobación.
`fecha_acuerdo`, `fecha_aprob` y `fase` quedan nulos: ni el índice ni las fichas
verificadas proporcionan esos datos. No se interpretan fechas dentro de los
PDF ni se declara aprobación, ejecución de obra o vigencia jurídica actual.
No se fabrican coordenadas; `geometry`, `lat` y `lon` quedan nulos y
`publication_ready=false`.

## Límites y comportamiento

Es una instantánea completa **del inventario Desarrollo del PGOU visible**,
con cobertura municipal parcial. No es un registro histórico exhaustivo ni
incluye todas las modificaciones, la revisión del PGOU, noticias, contratación,
licencias concedidas o formularios. Los documentos se conservan como enlaces;
no se descarga ni interpreta su contenido en el adaptador.

La extracción no aplica cortes de fecha ni límites de número de registros.
Ante paginación nueva, índice vacío, título desconocido, fecha inválida,
duplicados contradictorios, redirección inesperada, discordancia de títulos o
ficha sin documentos, falla antes de reemplazar la salida. Una futura paginación
requiere ampliar el crawler; no se acepta silenciosamente una primera página.
La actualización vuelve a extraer la instantánea íntegra. Licencias,
planificación automática y jitter están deshabilitados en el manifest.

## Verificación y evidencia local

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `python -m unittest municipio.test_astigarraga -v`: **6 pruebas correctas**.
  Cubren separación de fechas, agrupación/procedencia documental, identidad
  estable, rechazo de entradas ajenas, paginación, fechas inválidas, discordancias,
  documentos ausentes, duplicados contradictorios y conservación de salida previa
  ante fallo, además de manifest y licencias deshabilitadas.
- Extracción real mediante `load_manifest`, `load_portal_adapter` y
  `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **5 registros y 21
  enlaces documentales**, sin cortes de paginación.
- `evidence/validation.json`: recuentos, URLs consultadas, fecha de comprobación,
  limitaciones y resultado del adaptador/capa compartida de anotación.
- `evidence/captures/`: HTML de índice y cinco fichas capturado por el adaptador,
  con mapa URL/archivo en validation.json. Otros HTML bajo evidence documentan
  el descubrimiento de los inventarios generales.

La evidencia es local, no forma parte de los cuatro archivos fuente y no se
ha publicado ni enviado a servicios externos.
