# les Alqueries / Alquerías del Niño Perdido — INE 12901, Castellón

Investigación y extracción en vivo: 9 de noviembre de 2026.

## Descubrimiento y fuentes

La portada oficial https://www.lesalqueries.es/ identifica el Ayuntamiento y enlaza la sede electrónica. El mapa https://www.lesalqueries.es/es/sitemap permite descubrir **Urbanismo**, https://www.lesalqueries.es/es/administracion/urbanismo . Este inventario municipal es la fuente del adaptador, no una lista precargada de actuaciones. Su contenido actual presenta seis apartados numerados. El contenedor `main .cuerpo-taxo` contiene títulos h3 y enlaces documentales entre cada título y el siguiente. No se observó paginación; el parser rechaza indicadores de paginación para evitar truncamientos silenciosos. Se procesa toda la página, sin límite de registros ni corte por fechas.

También se inspeccionó https://lesalqueries.sedelectronica.es/transparency : muestra una categoría «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» con 85 documentos. La navegación usa llamadas Wicket con tokens de sesión; el intento de expansión devolvió respuesta vacía. No se incorpora esa categoría al scraper ni se afirma cobertura de esos 85 documentos. No se consultan expedientes privados.

## Cobertura y agrupación

Resultado real: **4 registros, 43 enlaces documentales**, agrupados según los apartados municipales:

- San Ramón — rehabilitación de edificio municipal para usos socio-culturales: 2 enlaces, proyecto eléctrico y proyecto básico/de ejecución del mismo edificio.
- PGOU 2015: 19 enlaces, anuncio de información pública, memorias, estudios, fichas, catálogo y documentación ambiental/paisajística del mismo instrumento.
- Proyecto de reparcelación unidad Joan Fuster: 15 enlaces, memoria, fichas y planos, incluidas sus carátulas.
- PAI Golf Subirana: 7 enlaces, resolución de adjudicación y documentación de planeamiento, ordenación, viario, dotaciones y unidades de ejecución.

Se excluyen el convenio Camí la Ratlla (el título por sí solo no acredita proyecto físico concreto) y la licencia ambiental de industria hortofrutícola (no se ha verificado una concesión). No se extraen formularios, anuncios de contratación ni noticias como proyectos. Licencias deshabilitadas.

La fuente documental es el Ayuntamiento; el alojamiento es Google Drive. Cada documento conserva su título, enlace completo y `provenance_url` municipal. Se deduplican enlaces dentro de un instrumento, nunca se mezclan entre apartados. Los identificadores se derivan del título del apartado, sin depender de su número de orden. Los documentos auxiliares no producen actuaciones independientes.

## Semántica y límites

La presencia en esta web no acredita vigencia, aprobación ni ejecución. En particular, el visor del primer documento del PAI se titula `anuncio_acuerdo_plenario_de_16_de_mayo_de_2017_de_resolucion_de_la_adjudicacion_del_pai_golf_subirana_.pdf`: no se interpreta como nuevo proyecto aprobado o activo. Se conserva como conjunto documental de un instrumento histórico. El año 2015 del PGOU permanece en su título y no se convierte en fecha de aprobación o publicación. No se deducen fechas de nombres de archivo; `fecha`, `fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan nulos, igual que `fase`.

No hay coordenadas ni geometrías verificadas: quedan nulas, `geometry_status: unavailable`, `publication_ready: false`. No se afirma cobertura exhaustiva del municipio, del historial urbanístico ni de obras actuales. Se refresca el inventario completo en cada actualización. `schedule.enabled=false`, `geocode.jitter_missing=false`, `licencias.enabled=false`.

## Validación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`python -m unittest municipio.test_les_alqueries -v`: cuatro pruebas correctas. Cubren agrupación y separación documental, exclusiones, fechas/coordenadas ausentes, estabilidad de identificadores, deduplicación, fallo ante estructura vacía o documentos ausentes y rechazo de paginación.

Ejecución real mediante `load_manifest('les-alqueries')`, `load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con `portal.config.capture_dir='evidence'` solo durante la comprobación local. Se verificó así también la resolución del adaptador por el manifiesto y el contrato compartido. La anotación existente de entidades clasifica los cuatro registros como `unknown`; no se fuerza su publicación.

Evidencia local no destinada a commit: `evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/urbanismo-live.html`, capturas de portada/mapa/transparencia y cuatro capturas `document-view-*.html`. Una muestra de visor por instrumento devolvió HTTP 200 con título PDF coherente (BT EDIF. SOCIO-CULTURAL, pgou_preliminar_alquerias, fichas_parcelas y anuncio de resolución de adjudicación del PAI). Se comprobaron los visores, no se descargaron ni analizaron íntegramente los 43 documentos; no se garantiza disponibilidad pública futura de todos los adjuntos. Sin geocodificación, base de datos, programación, publicación o despliegue.
