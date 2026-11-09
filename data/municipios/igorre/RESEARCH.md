# Igorre — Bizkaia — INE 48094

Verificación en vivo: 2026-11-09. Adaptador específico de la colección documental
municipal del Plan General de Ordenación Urbana (PGOU). Cobertura parcial municipal:
un instrumento real, agrupando sus fases; no es un inventario de todas las obras,
licencias o instrumentos vigentes de Igorre.

## Descubrimiento y elección de fuentes

La portada https://www.igorre.net redirige a la versión euskera. Su menú se carga
mediante JavaScript; las listas públicas de navegación SharePoint, usadas por
`/style%20library/ganekogorta/js/ganekogorta.js`, permiten descubrir Normativa
municipal y Anuncios sin autenticación. Capturas de portada, script y menús bajo
`evidence/`. Solo se consultó contenido público.

- [Normativa municipal](https://www.igorre.net/es-ES/Ayuntamiento/Normativa_municipal/Paginas/default.aspx)
  enlaza expresamente el PGOU.
- [Urbanismo](https://www.igorre.net/es-ES/Servicios/Urbanismo/Paginas/default.aspx)
  ofrece Planeamiento urbanístico, Convenios urbanísticos, PGOU y proyectos
  Gabolan e Igorreko Industrialdea. Los últimos quedan fuera de este adaptador;
  no se convierten sus enlaces de navegación en registros adicionales.
- [Colección del PGOU](https://www.igorre.net/es-ES/Servicios/Urbanismo/Paginas/PlanGeneraldeOrdenacionUrbana.aspx):
  fuente operativa, descubierta desde las secciones anteriores. Contiene enlaces
  a «Aprobación inicial del PGOU» y «Aprobación provisional del PGOU».
  Se siguen esas páginas, los índices técnicos, sus apartados y la paginación.
  No se usa un anuncio individual como semilla ni una lista fija de documentos.
- [Tablón general](https://www.igorre.net/es-ES/Ayuntamiento/Anuncios/Paginas/default.aspx):
  primera página observada de 143 anuncios, entre ellos PGOU y reurbanización de
  Garbe. No se extrae este tablón: sus 143 entradas no equivalen a proyectos ni a
  licencias concedidas y solo se inspeccionó su primera página para investigación.
- [Catálogo oficial foral de planeamiento de Igorre](https://www.opendatabizkaia.eus/es/catalogo/planeamiento-urbanistico-igorre):
  se descargó el JSON de Datos globales 2023-2026. Contiene estadísticas trimestrales
  de suelo y viviendas, no expedientes individualizados; no genera registros.
  La captura `globales.json` conserva la evidencia de esa exclusión. El propio
  catálogo advierte del carácter orientativo de los datos frente a documentos
  normativos originales.

## Resultado y semántica

La ejecución real del adaptador produjo `evidence/proyectos.jsonl`: **1 registro,
194 documentos únicos, 32 páginas HTML consultadas**. La fase inicial contiene
98 documentos y la provisional 96. El identificador `igorre-proy-pgou` permanece
estable aunque cambien los documentos o se añada una fase. Cada documento conserva
URL, título y todas sus procedencias (página y fase); una memoria, plano, guía de
participación o anuncio dentro de esta colección no constituye otro proyecto.

La fase del instrumento se obtiene de las etiquetas de aprobación del índice:
en la captura actual, aprobación provisional. No se afirma aprobación definitiva.
El [anuncio BOB enlazado por la fase provisional](https://www.igorre.net/es-ES/Servicios/Urbanismo/2026pgouaprobacionprovisional/01-bob-cas.pdf)
se capturó como `evidence/bob.pdf` y se inspeccionó mediante `pdftotext` (texto en
`bob.txt`): distingue el acuerdo del Pleno de **22-07-2026** de su publicación en
el BOB de **04-08-2026**. Es comprobación documental de investigación, no una regla
de extracción ni una fecha fijada en código.

El adaptador **no interpreta las fechas de los PDF**: `fecha`,
`fecha_publicacion`, `fecha_acuerdo` y `fecha_aprob` quedan nulas. Los años 2024/2026
en las rutas o encabezados no se convierten en fechas de aprobación/publicación.
Los PDF se retienen como enlaces documentales; no se descarga ni interpreta todo
su contenido. La captura de un anuncio no acredita por sí sola su vigencia futura.

## Paginación y fallos explícitos

Se recorren todos los enlaces de contenido del PGOU y todos los enlaces del
paginador `?page=N`, deduplicando URL y evitando ciclos. Se verifican documentos
únicos por listado SharePoint contra sus totales, incluso cuando varios listados
comparten página y parámetro de paginación. Validación real:

| Listado | Documentos esperados / extraídos |
| --- | --- |
| Inicial, planos EsECIA | 31 / 31 |
| Inicial, ordenación pormenorizada | 12 / 12 |
| Inicial, ordenación estructural | 23 / 23 |
| Inicial, información | 13 / 13 |
| Provisional, información | 13 / 13 |
| Provisional, ordenación pormenorizada | 12 / 12 |
| Provisional, ordenación estructural | 24 / 24 |

Un cambio de total durante el recorrido, paginador desconocido, enlace de contenido
inesperado, pérdida de fases, página vacía o discrepancia final falla sin reemplazar
la salida anterior. El límite de 100 páginas es una protección con error explícito,
no un truncamiento. `update_proyectos` vuelve a recorrer toda la colección y no
aplica cortes por fecha. Las capturas HTML tienen nombres derivados de su URL;
`evidence/validation.json` incluye el mapa completo URL → captura y los conteos.

## Geometría y límites

`geometry_status: unavailable`. Se publican planos PDF, pero no se ha verificado
geometría vectorial asociada al identificador del PGOU. No se digitalizan planos ni
se asigna el centroide municipal al instrumento. `geometry`, `lat` y `lon` son
nulos; `publication_ready` es falso. No se infieren coordenadas o CRS.

No se ha verificado un registro público de licencias concedidas. Los métodos de
licencias escriben una colección vacía con estado `disabled`; impresos, solicitudes,
contratos y noticias no se tratan como concesiones. Manifest con provincia Bizkaia,
INE `48094`, `licencias.enabled: false`, `schedule.enabled: false` y
`geocode.jitter_missing: false`.

## Validación reproducible

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_igorre -v` usando ese runtime: **7 pasan**.
Cubren agrupación y procedencia, deduplicación, páginas múltiples y listados
simultáneos, repetición de resultados incompletos sin sobrescribir la salida,
paginadores desconocidos, contenido ausente/ajeno, fechas y geometría nulas,
manifest y licencias deshabilitadas.

Extracción real: `IgorreAyuntamientoAdapter('igorre', {'capture_dir': 'evidence'}).backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
El informe local `evidence/validation.json` incluye `live_records`, `source_urls`,
limitaciones, conteos y comprobaciones de paginación. Evidencias locales excluidas
del código a entregar. Sin cambios de dependencias o fuentes compartidas, ni
publicación, despliegue o acceso a bases de datos.
