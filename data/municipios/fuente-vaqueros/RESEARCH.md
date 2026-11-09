# Fuente Vaqueros — Granada — INE 18079

Investigación y comprobación en vivo: 9 de noviembre de 2026.

## Inventario oficial y cobertura

Fuente: https://www.fuente-vaqueros.com/normativa/ . El sitio se identifica como
Ayuntamiento de Fuente Vaqueros, La Paz y Pedro Ruiz, con dirección en Fuente
Vaqueros, Granada. La sección «Documentación urbanística de Fuente Vaqueros»
contiene seis tarjetas, cada una con una página documental propia y un PDF
en el dominio municipal. Se recorren las seis páginas, no las noticias del CMS.
No se observó paginación en el índice ni en las páginas de documentos. El
adaptador falla si encuentra paginación o cambia el conjunto de secciones;
no recorta resultados ni declara cobertura de páginas no recorridas.

Dos instrumentos reales, agrupados tras comprobar las portadas:

* **PGOU — Adaptación parcial a la LOUA de las NNSS**: [memoria](https://www.fuente-vaqueros.com/normativa/memoria-de-adaptacion/),
  [planos de adaptación](https://www.fuente-vaqueros.com/normativa/planos-adaptacion/),
  [planos informativos](https://www.fuente-vaqueros.com/normativa/planos-informativos/)
  y [planos de infraestructura](https://www.fuente-vaqueros.com/normativa/planos-infraestructura/).
  La memoria nombra expresamente el PGOU y la adaptación parcial. Las primeras
  láminas de los tres paquetes de planos muestran ese mismo instrumento en
  el cajetín. Infraestructura es documentación del plan, no una obra ejecutada.
* **Normas Subsidiarias de Planeamiento — Revisión**:
  [anexo memoria](https://www.fuente-vaqueros.com/normativa/anexo-memoria/) y
  [planos NNSS](https://www.fuente-vaqueros.com/normativa/planos-nnss/).
  Sus portadas escaneadas dicen «Normas Subsidiarias de Planeamiento de Fuente
  Vaqueros. Revisión». Por ello el anexo no se asigna a la adaptación, pese a
  estar situado entre sus tarjetas en el índice.

Enlaces PDF efectivamente publicados, obtenidos de cada página hija:

* https://www.fuente-vaqueros.com/wp-content/uploads/memoria_adaptacion_fuente_vaqueros.pdf
* https://www.fuente-vaqueros.com/wp-content/uploads/planos_adaptacion.pdf
* https://www.fuente-vaqueros.com/wp-content/uploads/planos_informativos.pdf
* https://www.fuente-vaqueros.com/wp-content/uploads/planos_infraestructura.pdf
* https://www.fuente-vaqueros.com/wp-content/uploads/ANEXO-MEMORIA-1.pdf
* https://www.fuente-vaqueros.com/wp-content/uploads/NNSS_FUENTE-VAQUEROS.pdf

Los seis respondieron HTTP 200, `application/pdf`, con firma `%PDF-1.6`.
Se guardaron los PDFs completos y las siete páginas HTML en `evidence/`.
Las primeras páginas se inspeccionaron con `pdftotext` y representaciones PNG
locales de los documentos escaneados y planos. La variante real del título
«Planos adaptación» en la página hija se contempla explícitamente; su tarjeta
del índice dice «Planos de adaptación».

## Semántica y límites

Resultado: **dos registros y seis documentos**, conservando enlaces directos,
página de procedencia de cada documento e índice de origen. Los identificadores
son locales y estables por instrumento; no se presentan como expedientes
administrativos oficiales. Los duplicados del botón de descarga y del visor
PDF se eliminan dentro de cada página.

Es una biblioteca publicada actualmente que contiene documentación histórica,
no una afirmación de vigencia actual ni de cobertura histórica exhaustiva.
No se extraen las modificaciones mencionadas en la memoria como instrumentos
independientes sin fichas documentales verificadas. No se cubren licencias
concedidas, contratos, anuncios de licitación ni todo el conjunto de obras
municipales. La sede electrónica enlazada desde el sitio es
https://fuentevaqueros.sedelectronica.es/; no se usa como inventario de concesiones.

Sin fechas de publicación o acuerdos verificadas a nivel de registro. La fecha
04/10/2010 que figura en los planos es una fecha documental, no una aprobación
ni una publicación, y no se traslada a esos campos. Tampoco las referencias a
acuerdos históricos de las NNSS en la memoria se atribuyen a la adaptación.
No se infiere fase administrativa, fecha de concesión ni coordenadas a partir
de los mapas o de la dirección del ayuntamiento. `publication_ready: false`,
`geometry_status: unavailable`, licencias y programación desactivadas,
`geocode.jitter_missing: false`.

## Verificación reproducible

Runtime utilizado, sin instalaciones:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_fuente_vaqueros -v` (cinco correctas).
Comprueban agrupación y aislamiento entre instrumentos, deduplicación de PDFs,
procedencia, fechas ausentes, títulos reales, identificadores estables y rechazo
de páginas incompletas, formularios sin PDF, documentos externos y paginación.

Extracción real mediante `load_manifest('fuente-vaqueros')`,
`load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`.
`evidence/validation.json` contiene recuento vivo, fuentes, limitaciones,
resultado del adaptador y huellas de las capturas. Evidencia local, no fuente
versionada. No se ha ejecutado publicación, geocodificación ni acceso a bases
de datos.
