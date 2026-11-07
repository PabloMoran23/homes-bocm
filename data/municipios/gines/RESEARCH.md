# Gines (Sevilla), INE 41047

Investigación y extracción real: 7 de noviembre de 2026. Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Se revisaron `municipio/manifest.py`, el contrato `municipio/adapters/portal.py`,
el registro de adaptadores y el ejemplo Chipiona antes de implementar.

## Inventario oficial y alcance

Punto de entrada: https://transparencia.gines.es/es/ (portal municipal desarrollado por INPRO).
El adaptador descubre allí los enlaces de los indicadores 50 y 53 y descarga sus
galerías completas. No utiliza buscadores ni noticias como registros sintéticos.

- [PGOU y planos](https://transparencia.gines.es/es/transparencia/indicadores-de-transparencia/indicador/P.G.O.U.-APROBADO-DEFINITIVAMENTE-POR-LA-COMISION-PROVINCIAL-DE-ORDENACION-DEL-TERRITORIO-Y-URBANISMO-DE-SEVILLA-EL-6-DE-NOVIEMBRE-DE-2013-PUBLICADO-EN-EL-BOJA-N-78-DE-24-DE-ABRIL-DE-2014.-00001/): ocho documentos (memoria, planos de información y ordenación, normas, catálogo, estudio ambiental, estudio económico y anexo de movilidad), agrupados en un registro.
- [Modificaciones no estructurales del PGOU](https://transparencia.gines.es/es/transparencia/indicadores-de-transparencia/indicador/Modificaciones-al-P.G.O.U.-de-Gines-que-no-afectan-a-su-ordenacion-estructural./): seis documentos de la modificación 2017–2019, agrupados en otro registro. Conserva documento de 2017, ampliación de enero de 2019, valoración de impacto en salud, edicto de aprobación provisional, documento técnico con diligencia y publicación en BOP de noviembre de 2019.

La sección de normativa (indicador 56) duplica el PGOU en otra carpeta; no se
cuenta como un instrumento adicional. Cada documento conserva título, URL PDF y
URL de la ficha que lo publica. Los IDs dependen de la URL de la ficha, no del
orden o de la cantidad de documentos. La extracción observada contiene **2 registros
con 14 enlaces documentales**. Las galerías observadas no tienen paginación;
se recorren todos sus enlaces. Si aparecen controles de paginación reconocibles,
se produce error explícito en vez de devolver una página parcial. También fallan
la desaparición de categorías, las galerías vacías o documentos inesperados.

## Otras fuentes descubiertas y cobertura parcial

- https://gines.nuevoplan.es/ y https://gines.nuevoplan.es/documentos/:
  web del nuevo PGOM con documentos de las fases 1, 2 y 3 (incluido avance y documentos ambientales).
  Se inspeccionaron pero no se incluyen en este adaptador de transparencia.
- https://ayuntamientodegines.es/2024/04/16/el-ayuntamiento-de-gines-inicia-la-redaccion-del-nuevo-plan-general-de-ordenacion-municipal-pgom/:
  referencia municipal a la elaboración del nuevo instrumento; no es por sí sola
  un proyecto de obra ni una licencia concedida.
- https://ayuntamientodegines.es/2025/08/05/informacion-publica-sobre-la-aprobacion-inicial-de-la-innovacion-del-pgou/:
  comunicación oficial con enlace técnico PDF, inspeccionada y no incorporada al
  inventario seleccionado. Declara acuerdo de 31 de julio de 2025 y publicación
  de 5 de agosto de 2025, fechas distintas; no se trasladan a otros instrumentos.
- https://www.lineaverdegines.com/lv/documentos.asp?docu=Documentacion:
  inventario localizado en búsqueda, no integrado; mezcla ordenanzas, modelos y planeamiento.
- La sede electrónica ofrece trámites y solicitudes. No se verificó un registro
  público de concesiones. `licencias.enabled: false`.

La cobertura no es exhaustiva ni histórica de todos los expedientes municipales.
No se extraen licitaciones, formularios, noticias generales ni actuaciones físicas
por inferencia. Se publica lo que el inventario mantiene disponible en la fecha
de consulta, sin afirmar que esté actualizado jurídicamente ni reconciliarlo con
el nuevo PGOM o la innovación de 2025.

## Semántica y ejecución

El título del PGOU distingue aprobación definitiva de 6 de noviembre de 2013 y
publicación BOJA de 24 de abril de 2014. Se conserva como texto fuente, sin
convertirlo en una fecha genérica ni deducir acuerdos desde nombres de archivo.
No se analizan los contenidos íntegros de los PDF, no se rellenan fechas, fases,
coordenadas ni geometrías. `publication_ready: false`, `geometry_status: unavailable`.
La programación y el jitter están desactivados. `update_proyectos` vuelve a obtener
el inventario completo, sin afirmar seguimiento incremental de expedientes.

Pruebas: `python -m unittest municipio.test_gines -v`, **4 correctas**. Cubren
agrupación y deduplicación, separación de instrumentos, ausencia de fechas y
coordenadas inferidas, rechazo de cambios/vacíos/paginación, descubrimiento y
carga real del manifiesto con HTTP simulado.

La ejecución viva utilizó `load_manifest('gines')`, `load_portal_adapter` y
`backfill_proyectos`, incluida la anotación de política del registro compartido.
Evidencia local sin commit: `evidence/proyectos.jsonl`, `evidence/validation.json`,
`evidence/transparencia-index.html`, `evidence/pgou.html`,
`evidence/modificaciones.html` y capturas adicionales de descubrimiento.
Se comprobaron 1024 bytes iniciales del primer PDF de cada galería: HTTP 200,
`application/pdf` y firma `%PDF-` correctos; muestras en
`evidence/document-sample-0.bin` y `evidence/document-sample-1.bin`.
No se descargaron ni validaron íntegramente los catorce PDF.
