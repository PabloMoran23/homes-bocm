# Valmojado — INE 45180, Toledo

Investigación y extracción: 9 de noviembre de 2026.

## Inventario oficial y alcance

Fuente implementada: https://www.valmojado.com/normas-subsidarias/
Página del Ayuntamiento, sección Gestiones → Normas Subsidarias, con dirección
municipal en Valmojado (Toledo) y contacto de Urbanismo e Infraestructuras.
Se revisaron primero `municipio/adapters/portal.py`, el cargador de manifests y
los ejemplos de Chipiona y Manlleu. Se utiliza el contrato de cuatro métodos;
no se modifica el registro ni otro código compartido.

El inventario HTML contiene once enlaces PDF, todos en el dominio municipal,
agrupados en tres instrumentos:

- Normas Subsidiarias de Valmojado: normas urbanísticas, anexo de conceptos,
  memoria justificativa y seis planos (clasificación del suelo, estructura
  general, dos de ordenación/gestión y dos de viario/alineaciones/rasantes).
- Plan Parcial Ordenación SECTOR 3: un PDF.
- Plan Parcial Ordenación SECTOR 16: un PDF.

Los anexos y planos se conservan en `documentos`, con título literal, URL,
tipo documental y página de procedencia; no se cuentan como proyectos distintos.
Los identificadores corresponden al instrumento y no al nombre del PDF.
Los tres registros se derivan de enlaces vivos: no hay registros precargados.
La página observada es un listado estático único, sin paginación. El parser
rechaza indicadores de paginación nuevos, documentos PDF no clasificables,
redirecciones ajenas al inventario y cambios de título/contenedor, para evitar
una extracción parcial silenciosa. El refresco incremental repite el inventario
completo, sin filtrar por fechas del CMS.

## Fuentes adicionales y límites

La navegación municipal enlaza también
https://valmojado.sedelectronica.es/transparency/ . Su vista pública muestra
categorías de transparencia, incluida urbanismo/obras públicas/medio ambiente,
y un árbol dinámico con «Mostrar más». Se reconoce como fuente adicional,
pero este adaptador no extrae ese árbol ni actas, anuncios o contratación.
No se afirma cobertura municipal exhaustiva. Noticias, solicitudes de licencia
y anuncios de licitación no constituyen registros de proyectos ni concesiones.
No se ha verificado un inventario público de licencias otorgadas; sus métodos
están explícitamente desactivados y producen cero registros.

La portada del PDF de las Normas Subsidiarias identifica una aprobación
definitiva el 15 de julio de 2002 por la Comisión Provincial de Urbanismo.
Es un dato documental observado durante la investigación; el adaptador extrae
el inventario HTML, no interpreta los PDFs, por lo que deja todas las fechas y
fases sin informar. No utiliza la carpeta `/2011/12/`, fechas WordPress ni
la palabra `aprobado` del nombre del archivo del sector 3 como fechas de acuerdo.
Las fechas de publicación, acuerdo y aprobación son campos distintos, nulos.
La presencia en el inventario no garantiza vigencia consolidada ni ejecución.
No hay geometría geográfica verificada: coordenadas y geometría nulas,
`publication_ready: false`, `geocode.jitter_missing: false` y programación
`false`.

## Verificación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_valmojado -v`

Ocho pruebas cubren agrupación/deduplicación, aislamiento de sectores, rechazo
de navegación vacía y documentos extraños, paginación, fechas no inferidas,
refresco y captura, redirecciones sin sobrescribir resultados y manifest.

La ejecución real llama `ValmojadoAyuntamientoAdapter.backfill_proyectos` con
`config={'capture_dir': 'evidence'}` y destino `evidence/proyectos.jsonl`.
Genera tres registros con once enlaces documentales. La comprobación documental
descarga los once PDFs oficiales, comprueba HTTP 200 y firma `%PDF-` y conserva
archivos y hashes en evidencia. La primera petición de investigación con el
User-Agent por defecto de requests devolvió 403; el User-Agent explícito del
adaptador permite la extracción HTTP real. No se usa la caché del buscador como
entrada del scraper.

Evidencia local, fuera de los cuatro archivos fuente: `evidence/inventory.html`,
`evidence/proyectos.jsonl`, `evidence/validation.json` y `document-*.pdf`.
El JSON de validación recoge recuentos, URLs, resultados HTTP, hashes y límites.
No se ejecutan bases de datos, publicación, despliegue ni geocodificación.
