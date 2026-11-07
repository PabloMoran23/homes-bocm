# Pinos Puente — Granada — INE 18158

Investigación y extracción en vivo: 7 de noviembre de 2026. Se revisaron el
contrato `municipio/adapters/portal.py`, el cargador/esquema de manifests, el
registro dinámico y los ejemplos Chipiona y Hernani antes de implementar.

## Fuentes oficiales descubiertas

Directorio municipal: https://pinos-puente.org/ayuntamiento/ . Su apartado
Ordenación enlaza cuatro fuentes: Normas subsidiarias, PGOU, Plan Especial de
Protección de la Vega e Instrumentos de ordenación.

Se extraen estas dos fuentes documentales completas dentro de su página:

* https://pinos-puente.org/ayuntamiento/plan-general-de-ordenacion-urbana/ :
  **un PGOU con 78 documentos**. Memoria, normativa, catálogo, inventario,
  información/diagnóstico, estudios ambiental, sanitario y de inundabilidad,
  servidumbres y planos. Las secciones territoriales no son actuaciones
  independientes; cada documento conserva título, URL y sección.
* https://pinos-puente.org/ayuntamiento/instrumentos-de-ordenacion/ :
  **dos instrumentos con tres documentos cada uno**: modificación del plan
  parcial del Parque Industrial El Turán (SUBS-P4) y estudio de detalle de la
  unidad Z-7. Cada panel mantiene juntos su acuerdo, memoria y planos, sin
  mezclar los directorios `2024-3365-Turan` y `2024_3866_Z7`.

El adaptador descubre esas URLs a través del directorio oficial en cada ejecución.
No usa resultados precargados, búsquedas de noticias ni anuncios de contratación.
Los identificadores derivan del instrumento/directorio, no del ID temporal del
acordeón. La actualización vuelve a extraer el inventario completo y reemplaza
atómicamente el archivo tras validar todas las fuentes. No modifica el estado
incremental ni acumula versiones documentales antiguas.

## Fechas, estado y límites

El directorio describe el PGOU como aprobado provisionalmente el 4/10/2023.
Como corroboración independiente se consultó
https://www.juntadeandalucia.es/boja/2023/223/88 : identifica el expediente
2118/2018, el acuerdo de 4 de octubre de 2023, el anuncio de 19 de octubre y
el boletín de 21 de noviembre de 2023. Son fechas de distinta naturaleza.
El scraper no incorpora ninguna de ellas como fecha genérica ni afirma aprobación
definitiva del PGOU. Tampoco convierte fechas del CMS, nombres de ficheros o
directorios en fechas de aprobación/publicación. Los títulos de El Turán y Z-7
se conservan como los publica el Ayuntamiento, sin deducir fechas de sus PDFs.

Cobertura **parcial**: no es un registro histórico completo ni un inventario de
todas las obras públicas. Se inspeccionó
https://pinos-puente.org/ayuntamiento/normas-subsidiarias/ (15 enlaces PDF,
incluida adaptación parcial), pero queda fuera del alcance de estas dos fuentes.
https://pinos-puente.org/ayuntamiento/plan-especial-de-proteccion-de-la-vega/
respondió HTTP 521 en el sondeo y también queda excluida. No se inventa un registro
para esa fuente. Las dos páginas extraídas mostraron todos sus acordeones en una
respuesta y ninguna paginación; el parser falla explícitamente si detecta
paginación en vez de truncar resultados. Se rechazan contenedores vacíos,
paneles desconocidos, documentos externos y agrupaciones ambiguas.

El portal respondió inicialmente 403/521 en algunas peticiones; los alias
oficiales www y sin www permiten la extracción con User-Agent Mozilla/5.0.
Se prueban ambos alias de forma acotada y cualquier fallo final se propaga.
No se utilizan credenciales ni sesiones autenticadas.

Los registros tienen `publication_ready: false` y `geometry_status: unavailable`.
No hay coordenadas ni geocodificación artificial. Licencias desactivadas:
no se ha verificado un inventario público de concesiones. Schedule desactivado.
Los enlaces documentales se conservan sin afirmar accesibilidad universal,
vigencia jurídica actual, ejecución física ni lectura integral de los PDFs.

## Verificación reproducible y evidencias locales

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Tests: `python -m unittest municipio.test_pinos_puente -v` (8 pruebas).
Cubren aislamiento documental, agrupación PGOU, procedencia de secciones,
ausencia de fechas/coordenadas inferidas, rechazo de formularios/vacíos,
dominios externos y paginación, preservación del archivo ante fallo, licencias
desactivadas, resolución por manifest y fallback entre hosts oficiales.

Extracción real mediante `load_manifest('pinos-puente')`,
`load_portal_adapter(manifest).backfill_proyectos(Path('evidence/proyectos.jsonl'))`,
con `manifest.portal.config['evidence_dir']` apuntando al directorio local.
Resultado: **3 registros y 84 enlaces documentales**. El guard compartido de
entidades devuelve status `ok`; sus categorías figuran como desconocidas, sin
impedir la conservación documental ni convertir registros en publicables.

`evidence/validation.json` registra conteo, fuentes, límites y comprobaciones.
Se guardan las tres páginas usadas por el adaptador, sondeos de descubrimiento
y el BOJA consultado (`probe-3.html`). Se comprobó el primer PDF de cada
instrumento: HTTP 206, `application/pdf` y firma `%PDF-`; se conservan únicamente
los primeros 1024 bytes de cada muestra (`document-*-prefix.bin`). No se ha
descargado ni verificado íntegramente todo el conjunto de 84 documentos.
Las evidencias son locales y no forman parte de los cuatro archivos fuente.
