# Pozuelo de Calatrava — INE 13066, Ciudad Real

Investigación y extracción real: 9 de noviembre de 2026. Municipio de Castilla-La Mancha; no confundir con Los Pozuelos de Calatrava (13067), Pozuelo (Albacete) ni Pozuelo de Alarcón (Madrid).

## Fuentes oficiales descubiertas

- Web municipal: https://www.pozuelodecalatrava.es/ . Enlaza tanto la sede provincial como el portal de transparencia.
- Archivo municipal actual: https://www.pozuelodecalatrava.es/actualidad . La categoría «Obras», https://www.pozuelodecalatrava.es/actualidad.php?c=2 , devuelve «No se han encontrado noticias». No se interpreta como ausencia de obras.
- Inventario usado: https://www.pozuelodecalatrava.es/actualidad.php?d=20260101&h=20261231&p=1 . Archivo de noticias filtrado por fechas, no registro administrativo de expedientes. Se han recorrido las **9 páginas y 85 noticias** del filtro anual de 2026, hasta el control terminal sin avance. Las flechas tienen etiquetas inversas a la cronología: ANTERIOR aumenta el número de página. El adaptador lee `frmPaginacion` y `fncPaginacion(n)`, conserva los filtros y verifica que el servidor los respete. Un ciclo, salto, página repetida, cambio de estructura o crecimiento superior al límite de seguridad produce error sin escribir resultados parciales.
- Transparencia: https://pozuelodecalatrava.transparencialocal.gob.es/ . Falló por certificado caducado en requests. No se desactivó la verificación TLS.
- Sede: https://sedescr.dipucr.es/pozuelo-de-calatrava/ . El buscador muestra trámites y tablón con anuncios de personal y cuentas, con paginación. requests falla por cadena de certificado. Ese tablón no forma parte de la extracción ni se afirma haberlo recorrido. Un trámite «Licencias de obra» es una solicitud, no una concesión.

## Cobertura y selección

Siete actuaciones físicas, obtenidas de ocho noticias oficiales con evidencia explícita de ejecución o inauguración en sus propios párrafos:

| Actuación | Noticias municipales (`/actualidad/ID/...`) | Publicación CMS |
| --- | --- | --- |
| Nuevo pabellón deportivo municipal | 2361 y 2400 | 15 enero y 2 junio de 2026 |
| Acondicionamiento y jardinería del Parque Municipal | 2399 | 26 mayo de 2026 |
| PERTE de digitalización y sectorización de la red de agua | 2398 | 25 mayo de 2026 |
| Renovación de parques infantiles | 2393 | 30 abril de 2026 |
| Guardapasos municipal | 2387 | 31 marzo de 2026 |
| Plantación de árboles en La Inesperada | 2380 | 12 marzo de 2026 |
| Plan de asfaltado de varias calles | 2379 | 12 marzo de 2026 |

Los enlaces completos se retienen en cada registro y en `evidence/validation.json`. Son siete temas revisados, seleccionados por título y confirmados por texto de ejecución; no un clasificador exhaustivo de todas las noticias. Los registros se construyen del contenido recuperado en cada ejecución, sin precargar noticias ni resultados en el código. La ausencia de obras verificables provoca error.

La noticia 2400 informa del nombramiento del pabellón y, además, de pilotaje y saneamiento ya realizados. Se agrupa con la noticia 2361 del inicio de obras, conservando ambas procedencias y sus fechas. No constituye una segunda obra. El título principal procede de la noticia más antigua; no se sintetiza un expediente nuevo. Los proyectos de mejora de parques y asfaltado conservan su alcance conjunto tal como los presenta el ayuntamiento; no se multiplican por calle o parque.

Se excluyen el anuncio de licitación del pabellón (2326), la noticia de adjudicación de redes (2373), la noticia centrada en adjudicación de acerados (2374), las bases de empleo y los formularios. La noticia 2359 sobre licencia para 27 viviendas tampoco se convierte en registro de concesión ni proyecto: licencias desactivadas. Las menciones secundarias a otras inversiones, actos deportivos, promoción turística y balances políticos no generan actuaciones adicionales.

## Semántica y limitaciones

Las noticias son documentación municipal de obras, sin sustituir proyectos técnicos, acuerdos ni actas de concesión. `fecha_publicacion` corresponde exclusivamente al CMS; cada documento conserva su propia fecha. No se atribuyen fechas de acuerdo, aprobación, inicio o finalización. No se convierte «hoy» o «Domingo de Ramos» en fecha absoluta. La noticia 2361 menciona la temporada 2025/26 pese a su publicación en enero de 2026: no se resuelve esa inconsistencia por inferencia.

`documentos` contiene las noticias agrupadas, evidencia textual de ejecución y enlaces a adjuntos de su propio contenedor. Las fotografías se identifican como tales; no se presentan como PDFs técnicos. No se descargan todos los adjuntos. Las referencias a intervenciones anteriores no se extraen como nuevos expedientes. No se afirma cobertura de planeamiento, licencias, todos los ejercicios ni todas las obras del municipio. `update_proyectos` vuelve a recorrer el mismo año 2026 y reemplaza el resultado, sin utilizar un cursor incremental. Los nuevos temas requieren revisión explícita de las reglas.

Sin coordenadas verificadas: `geometry_status: unavailable`, `publication_ready: false`. `schedule.enabled: false`, `geocode.jitter_missing: false` y `licencias.enabled: false` en el manifiesto. No se ha publicado, geocodificado ni conectado a bases de datos.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_pozuelo_de_calatrava -v
```

Siete pruebas pasan: paginación inversa y conservación de filtros; rechazo de estructura inválida, filtros ignorados y saltos; agrupación y procedencia de adjuntos; fechas de publicación; rechazo de formularios, licitaciones y noticias sin ejecución; carga del manifiesto/registro; recorrido de varias páginas y preservación del fichero previo ante errores.

Ejecución real mediante `load_manifest`, `load_portal_adapter` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **7 registros, 9 páginas, 85 noticias examinadas**, ocho noticias seleccionadas. `evidence/validation.json` contiene runtime, recuento, URLs de cada petición y limitaciones. `evidence/live/live-NNN.html` guarda las respuestas de esa ejecución en el mismo orden que `source_urls`; las capturas de investigación adicionales también están bajo `evidence/`. Evidencia exclusivamente local, fuera de los cuatro archivos fuente.
