# Villanueva del Río Segura — INE 30042, Murcia

Comprobado el 2026-11-09 con el Python preinstalado. Implementación limitada al
**PGMO documentado**, no al conjunto de obras o expedientes del municipio.

## Descubrimiento e inventario oficial

La portada https://www.villanuevadelsegura.es/ enlaza la Oficina Técnica,
Documentos online, información general de transparencia y la sede con entidad
30042. Las páginas de Oficina Técnica y Documentos online consultadas no ofrecen
un registro de licencias concedidas. Los servicios y formularios no acreditan
concesiones. No se ha verificado un inventario exhaustivo de la sede electrónica.

La fuente recorrida es el archivo municipal Joomla:
https://www.villanuevadelsegura.es/index.php . Extracción en vivo: **34 páginas**,
offsets 0–165, enlazadas por `ul.uk-pagination`; no se fija una última página en
el código. Se siguen todos los enlaces start/limitstart, incluidos los intermedios,
hasta agotar el grafo. Cambios de paginación no soportados, HTML ausente, páginas
repetidas o más de 200 páginas provocan error sin escribir resultados parciales.
Las noticias ajenas al PGMO, formularios, empleo y anuncios de contratación se
excluyen. Hay noticias de obras físicas en este archivo, pero no forman parte de
la cobertura implementada y no se convierten automáticamente en proyectos.

Se descubren estas tres publicaciones del mismo instrumento:

- https://www.villanuevadelsegura.es/index.php/174-exposicion-publica-parcial-del-plan-general-municipal-de-ordenacion-de-villanueva-del-rio-segura
  Acuerdo de subsanación del 27.07.2017, que cita una aprobación definitiva parcial
  de 01.03.2012. Seis PDF: normas, ordenación del casco/San Roque,
  Asunción/La Morra, Carmen, zonificación y fichas de suelo urbanizable.
- https://www.villanuevadelsegura.es/index.php/241-publicado-el-plan-general-municipal-de-ordenacion-de-villanueva-del-rio-segura-murcia
  Enlace a `/PGMO/PGMO_VILLANUEVA_ENERO_2019.pdf`. El nombre del archivo no
  establece una fecha de acuerdo, aprobación ni publicación.
- https://www.villanuevadelsegura.es/index.php/295-publicado-de-forma-definitiva-el-plan-general-municipal-de-ordenacion-de-villanueva-del-rio-segura
  Texto municipal: orden de 23 de junio de 2022, aprobación definitiva **parcial**
  y toma de conocimiento, expediente 309/04 de planeamiento.
  https://www.borm.es/services/anuncio/ano/2022/numero/3568/pdf?id=808916

Aunque el titular municipal de 2022 dice «definitiva», se mantiene el carácter
**parcial** que acredita su cuerpo. La captura inicial del BORM (PDF válido,
`evidence/borm-2022.pdf`, texto extraído en `borm-2022.txt`) acredita publicación
el **6 de julio de 2022**, distinta de la fecha de orden. Peticiones posteriores
al BORM devolvieron CAPTCHA con HTTP 200: se documenta la limitación sin eludirlo.
El adaptador extrae la fecha de orden del texto municipal; deja nula la publicación
municipal y no introduce una fecha de BORM constante sin analizar el documento.
El expediente aparece en la descripción original, sin inventar referencias.

## Agrupación, procedencia y límites

**Un instrumento real, tres publicaciones, ocho enlaces documentales únicos**.
Cada documento conserva las páginas municipales de procedencia, cada publicación
su descripción y fechas explícitas. No se generan ocho proyectos a partir de los
PDF. Los documentos históricos se conservan como tales: no se supone que los
planos de 2017/2019 sean el texto íntegro actualizado por la orden de 2022.
No se determina vigencia jurídica completa ni se extrae todo el desarrollo del
PGMO. La actualización repite el inventario completo y agrupa por identidad del
PGMO municipal, sin estado incremental que omita publicaciones antiguas.

Sin coordenadas ni geometría verificada. Los planos PDF no proporcionan aquí una
geometría vectorial asociada al registro; no se vectorizan, geocodifican ni usan
centroides. `publication_ready=false`, `schedule.enabled=false`,
`geocode.jitter_missing=false` y `licencias.enabled=false`.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_villanueva_del_rio_segura -v`: tres pruebas
superadas, con agrupación/deduplicación/procedencia, separación de fechas, rechazo
de formularios y HTML inválido, recorrido de páginas intermedias y conservación
del resultado previo si falla una página.

Extracción real ejecutada mediante `load_manifest`, `load_portal_adapter` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con captura configurada en
`evidence/live/`. Resultado: un registro, 34 páginas y tres detalles. Evidencias
locales: `proyectos.jsonl`, `validation.json`, capturas HTML, comprobaciones de
respuesta de documentos y BORM. No requieren una dependencia nueva ni servicios
externos de publicación. Las evidencias no se incluyen entre los cuatro fuentes.
