# Sant Lluís — INE 07052, Illes Balears

Revisión y extracción en vivo: 2026-11-09. Adaptador exclusivo del municipio.
Se revisaron el contrato `municipio/adapters/portal.py`, el cargador de manifiestos,
el registro dinámico y los ejemplos de Hernani y Manlleu antes de implementar.

## Descubrimiento y fuentes oficiales

La portada https://www.ajsantlluis.org/ enlaza «Normes Subsidiàries» y el área
https://www.ajsantlluis.org/publicacions/area.aspx?ID=11 vuelve a enlazar el catálogo.
Las tres pestañas oficiales, todas HTTP 200, son:

- https://www.ajsantlluis.org/Contingut.aspx?IdPub=37089 — nuclis tradicionals i sòl rústic.
- https://www.ajsantlluis.org/Contingut.aspx?IdPub=37093 — zones turístiques.
- https://www.ajsantlluis.org/Contingut.aspx?IdPub=37100 — altres normatives urbanístiques.

El extractor parte del catálogo, descubre y recorre las pestañas enlazadas, sin
sembrar noticias ni documentos individuales. No se observó paginación activa.
Rechaza indicadores de paginación, cambios de estructura o grupos desconocidos;
el límite de seguridad de navegación provoca error, nunca resultados truncados.
Todos los documentos PDF enlazados en el contenido se conservan, sin límite de
cantidad. Los enlaces del menú general y del pie no se interpretan como registros.

## Resultado y semántica

Tres instrumentos reales, con **88 enlaces PDF**:

- Normes Subsidiàries de Sant Lluís: 82 documentos, agrupando los dos ámbitos
  documentales tradicional/rústico y turístico en un solo instrumento. Las memorias
  de modificación y sus informes se conservan dentro del conjunto documental;
  no se convierten en proyectos independientes sin expediente identificado.
- Pla Especial de Binifadet: tres documentos (plan, planos y BOIB).
- Pla Especial de Ses Barraques: tres documentos (plan, planos y BOIB).

Cada documento retiene título, URL municipal, sección y página de procedencia.
IDs estables derivados del nombre del instrumento, independientes del orden de enlaces.
El catálogo identifica los instrumentos; no se afirma una fase de aprobación a
partir de su mera presencia. Las fechas de publicación, acuerdo y aprobación son
nulas: no se extraen de los PDF ni se deducen de «2013» o «AGOST 2022» en rutas.
No se confunde una fecha de publicación con una de acuerdo.

Nucli Rural Camp Sarc solo ofrece una ordenanza y se excluye como recurso normativo.
AC2 «Servituds Aeròdrom i Instal·lacions Radioelèctriques» aparece como texto sin
hipervínculo: no se fabrica un documento ni su URL. El método de actualización
refresca la instantánea completa, sin inferir derogaciones ni tramitar bajas.

La Carpeta Ciutadana ofrece solicitudes, por ejemplo
https://www.carpetaciutadana.org/santlluis/gesserveis/gestion.aspx?IDGESTION=58&IDIOMA=1,
que no prueban concesiones; licencias deshabilitadas. Los anuncios de contratación
y el flujo general de noticias tampoco se usan como inventario de proyectos.
Se revisó https://www.ajsantlluis.org/Contingut.aspx?IdPub=34475, mapa de proyectos
participativos: no se incorpora su contenido embebido ni se infieren actuaciones
por el título de la página. La cobertura es parcial, exclusivamente el catálogo
urbanístico consultado, sin garantía de incluir todo el histórico o la tramitación.

## Geometría y validación

geometry_status: unavailable. Hay cartografía PDF, pero no geometría vectorial
vinculada a estos registros verificada. No se vectorizan planos ni se inventan
coordenadas o CRS; `publication_ready=false`, `lat/lon/geometry=null`.

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

- `python -m unittest municipio.test_sant_lluis -v`: seis pruebas pasan, cubriendo
  agrupación/deduplicación, procedencia, navegación, más de 50 documentos, rechazo
  de paginación/contenido inválido, fechas ausentes y licencias deshabilitadas.
- `SantLluisAyuntamientoAdapter(...).backfill_proyectos(Path('evidence/proyectos.jsonl'))`:
  extracción HTTP real, tres registros. Capturas del propio adaptador en
  `evidence/catalogue-*.html`.
- Un PDF representativo por instrumento descargado: normativa NNSS y los dos BOIB,
  HTTP 200 y firma `%PDF-` verificados. No se comprueban todos los 88 destinos.
- `evidence/validation.json` contiene recuentos, fuentes, capturas PDF con hashes y
  limitaciones; `evidence/proyectos.jsonl` contiene los registros reales.

La evidencia es local y no forma parte de los cuatro archivos fuente.
`schedule.enabled=false`, `geocode.jitter_missing=false`, `licencias.enabled=false`.
