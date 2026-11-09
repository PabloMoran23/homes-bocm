# Los Santos de Maimona — INE 06122, Badajoz

Comprobación en vivo: 2026-11-08. Fuente operativa: registro de planeamiento
SITEX, Junta de Extremadura. Cobertura parcial: instrumentos municipales con
estado **Vigente**, no una relación de obras ejecutadas ni de licencias concedidas.

## Descubrimiento y procedencia

- https://lossantosdemaimona.com/servicios/urbanismo/ y su variante www: HTTP 403
  desde requests en este entorno. La página describe servicios, no concesiones.
- https://old.lossantosdemaimona.com/transparencia/listadomenu.php?IdRelacion=17
  responde 200 pero entrega una cabecera incompleta sin inventario utilizable.
  La variante www.old presenta un certificado incompatible con el hostname;
  no se desactiva TLS.
- https://lossantosdemaimona.sedelectronica.es/transparency/ responde 200 con
  árbol Wicket dinámico. No se ha conseguido extraer de él un inventario estable
  de planeamiento. No se usan formularios de trámites como registros reales.
- https://sitex.juntaex.es/SITEX/planeamiento es el inventario oficial autonómico
  descubierto mediante búsqueda de planeamiento municipal. Su selector identifica
  `Santos de Maimona, Los`, ID interno **167** (no es el código INE).
  Su código público invoca `ptofiguras/listadoresultadossigcat` mediante POST.

El adaptador descubre el ID por nombre exacto en cada ejecución y hace POST a
https://sitex.juntaex.es/SITEX/ptofiguras/listadoresultadossigcat con
`municipioseleccionado=167`. GET no aplica ese filtro: se verifica el selector
municipal devuelto y se verifica también municipio, ID y estado de cada ficha.
No se fijan noticias individuales ni IDs de instrumentos como semillas.

La respuesta es un árbol completo: **81 instrumentos**, de ellos 10 vigentes,
9 en trámite y 62 no vigentes. Se recorren todos los enlaces del árbol y se
seleccionan únicamente los 10 vigentes, sin límite de registros. No hay
paginación en la respuesta observada. Controles de paginación futuros provocan
error explícito; nunca se acepta silenciosamente la primera página.

## Resultado y semántica

Una fila por ID de instrumento SITEX, con su referencia original y todos sus
trámites/documentos agrupados. Se obtuvieron **10 registros y 42 enlaces
 documentales únicos por instrumento**:

| SITEX | Referencia | Aprobación definitiva (campo SITEX) | Publicación AD (campo SITEX) | Documentos |
| --- | --- | --- | --- | --- |
| 37266 | PGM | 2010-05-27 | 2011-04-26 | 19 |
| 37409 | PGM.M-004 | 2014-08-28 | 2015-01-19 | 3 |
| 39026 | PGM.M-006 | 2015-10-29 | 2016-04-15 | 2 |
| 38981 | PGM.M-005 | sin dato | 2021-02-15 | 3 |
| 40196 | PGM.M-007 | 2023-04-27 | 2023-10-10 | 5 |
| 32914 | PGM.ED-001 | 2012-07-30 | 2012-08-17 | 2 |
| 39154 | PGM.ED-006 | 2015-12-29 | 2016-02-04 | 2 |
| 39340 | PGM.ED-007 | 2016-04-26 | 2016-06-14 | 2 |
| 39760 | PGM.ED-008 | sin dato | 2018-10-23 | 2 |
| 40625 | PGM.ED-010 | 2024-01-29 | 2024-07-01 | 2 |

Fichas: `https://sitex.juntaex.es/SITEX/ptofiguras/viewsigcat/{ID}`.
Se conserva `source_metadata` para auditar los campos y `tramites` para las
fechas de cada evento; `fecha_aprob` procede únicamente de `Fecha AD`,
`fecha_publicacion` de `Fecha de publicación AD`. No se usa una fecha genérica,
ni se infiere `fecha_acuerdo` de la publicación. Los dos campos AD vacíos
permanecen null, aunque existan otros trámites fechados.

Los campos resumen del registro no siempre coinciden con el evento DOE:
ED-001, ED-006 y ED-008 indican BOP en su resumen y tienen enlaces separados
a publicaciones DOE; ED-008 enlaza una ruta DOE de 2020 aunque el resumen
dice 2018. Se retienen ambos sin corregirlos por conjetura. La asociación de
cada documento procede de la ficha; no se afirma haber validado el contenido
de todos los PDFs ni que sus etiquetas estén libres de errores de catálogo.

Se descargaron y leyeron dos publicaciones como comprobación documental:

- https://doe.juntaex.es/pdfs/doe/2024/1260o/24081058.pdf confirma el estudio
  RE-198 y RE-197, acuerdo del Pleno de 29/01/2024, anuncio de 20/06/2024 y
  publicación el 01/07/2024. Son tres fechas distintas.
- https://doe.juntaex.es/pdfs/doe/2023/1950o/23AC0071.pdf confirma la
  modificación Sierra del Castillo, acuerdo CUOTEX de 27/04/2023 y publicación
  el 10/10/2023.

Los 42 enlaces incluyen publicaciones DOE y documentos técnicos SITEX, con
etiqueta original y `provenance_url`. Los formularios y menús comunes quedan
excluidos. Los documentos de un instrumento no generan filas adicionales.
Los HTTP originales del catálogo se conservan como procedencia; no se asegura
la disponibilidad actual de cada descarga no comprobada.

`source` de cada registro indica `sitex_junta_extremadura`. El valor
`proyectos.source: ayuntamiento` es el selector de pipeline del esquema existente,
no atribución de la custodia del registro al ayuntamiento. No se cambian fuentes
compartidas. El clasificador compartido deja el PGM genérico como pendiente por
carecer su referencia de dígitos; se conserva su identidad SITEX sin inventar un
número de expediente para alterar esa clasificación.

## Límites y geometría

No incluye los 71 instrumentos de otros estados, modificaciones aún en trámite,
obras municipales, contratación, noticias ni licencias. El estado Vigente es el
del registro en la fecha de consulta, no garantía independiente de consolidación
jurídica ni de exhaustividad municipal. Las actualizaciones repiten la instantánea
completa, porque documentos y metadatos pueden cambiar sin nueva fecha.

`geometry_status: unavailable`. El visor ofrece cartografía municipal de contexto
y documentos con planos, pero no se ha verificado geometría vectorial de cada
instrumento. No se atribuye el polígono municipal a los proyectos, ni se inventan
coordenadas, centroides, fechas o jitter. `publication_ready: false`.
`schedule.enabled: false`, `geocode.jitter_missing: false` y licencias deshabilitadas.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_los_santos_de_maimona -v`:
**7 pruebas pasan**. Cubren descubrimiento, filtro de estado, deduplicación,
municipio incorrecto, estructura/paginación inesperada, agrupación documental,
separación de fechas, ausencia de aprobación y conservación de salida previa
si falla una extracción. El manifiesto se carga con el loader real.

Extracción real ejecutada mediante `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con configuración local
`evidence_dir` para guardar capturas. HTTP con TLS, timeout de 40 s, pausa de
0,25 s por ficha, escritura tras validar todas las fichas. Sin DB ni publicación.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`,
`evidence/validation.json`, `sitex-discovery.html`, `sitex-inventory.html`,
`sumario de fichas: sitex-detail-{ID}.html`, dos PDFs DOE y su texto extraído.
`validation.json` registra cantidad real, fuentes, fecha de ejecución y limitaciones.
