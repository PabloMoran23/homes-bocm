# Campillos — Málaga — INE 29032

Verificación en vivo: 2026-11-08. Adaptador específico para la sede electrónica
oficial, contrato `AyuntamientoAdapter`, cargable mediante el registro existente.
Se revisaron previamente `municipio/manifest.py`, `municipio/adapters/portal.py`,
registro y ejemplos de Chipiona, Hernani y Manlleu. No se modifican fuentes compartidas.

## Descubrimiento y fuentes oficiales

- https://www.campillos.es/ — peticiones directas devolvieron HTTP 202 sin contenido;
  el navegador de investigación tampoco obtuvo contenido utilizable (403).
  No se interpreta esta respuesta como inventario vacío.
- https://campillos.sedelectronica.es/transparency — responde 200, pero el contenido
  observado no expone un inventario de planes; su navegación pública sí enlaza el
  **Tablón de anuncios**.
- https://campillos.sedelectronica.es/board — inventario público vigente, HTTP 200.
  Tabla con documento, expediente, procedimiento, categoría, descripción y fecha de
  publicación. Se consulta sin autenticación, sin credenciales y sin áreas personales.
- El catálogo de trámites de la sede ofrece solicitudes, no concesiones verificadas.
  Se excluye como fuente de licencias. El perfil de contratante no se usa.
- La búsqueda también localizó el texto refundido histórico en
  https://static.malaga.es/municipios/subidas/archivos/7/4/arc_47047.pdf y anuncios
  históricos BOJA. No se convierten PDFs aislados encontrados por buscador en un
  supuesto inventario municipal completo o actualizado.

## Cobertura real y semántica

La ejecución real leyó **14 documentos en 2 páginas**, produjo **1 proyecto**:
expediente **3169/2025**, proyecto de actuación extraordinaria para ampliar
instalaciones existentes mediante una nave de almacenamiento de fardos de paja,
polígono 15, parcelas 28, 39 y 40, Campillos. Proyecto privado en suelo rústico;
no se presenta como obra pública ni licencia concedida.

Se agrupan por expediente los dos documentos de Urbanismo:

- [Proyecto de actuación](https://campillos.sedelectronica.es/preview-document/b6d53a7e-8d35-437d-9c58-397e60974062).
- [Anuncio de información pública](https://campillos.sedelectronica.es/preview-document/03cfe3c7-7aa2-43a0-9d46-e86a283125ec).

El título sustantivo se obtiene del PDF del proyecto, no se inventa a partir de la
categoría. Los enlaces estables a las vistas de documentos se conservan junto a
sus títulos, expediente, procedimiento, descripción y fechas del tablón. El PDF
anunciador acredita expresamente información pública del mismo expediente.
`DEFINITIVA` en el nombre del archivo NO se interpreta como aprobación definitiva.
`Licencias Urbanísticas` en la columna procedimiento NO significa licencia otorgada.

Ambos documentos tienen fecha de publicación municipal **2026-10-27**. El anuncio
menciona Decreto 2026-2829 de **2026-09-17** de admisión a trámite y firma electrónica
de **2026-09-18**. No son fechas de aprobación del proyecto ni de concesión de licencia.
Se retiene ese pasaje como descripción documental; `fecha_acuerdo` y `fecha_aprob`
se dejan nulas. La creación del documento en la vista previa tampoco se convierte
en publicación. No se acredita aquí la fecha de publicación BOP ni el cierre del
plazo: la fase significa el trámite anunciado, no que el plazo siga abierto hoy.
La descripción extraída de PDF puede contener sellos y texto lateral de firma.

## Paginación, límites y comportamiento

El botón **Mostrar más** usa Wicket AJAX y tokens de sesión. El scraper mantiene
una sesión, descubre el token actual y procesa los componentes XML que añaden filas;
continúa hasta la sustitución del control por un contenedor oculto sin botón.
En la captura verificada, primera página de 10 documentos y segunda de 4, con
terminación explícita. No hay truncamiento silencioso: bucles, límite de seguridad
de 100 páginas, respuestas inesperadas o paginación no soportada provocan error
antes de escribir resultados. Documentos repetidos se deduplican por URL estable.

Filtro deliberadamente parcial: proyectos cuyo título de tabla identifica un
proyecto de actuación, categoría Urbanismo, agrupados por expediente; se verifican
el PDF sustantivo y anuncio de información pública. Otros tipos de instrumentos,
noticias, impresos, empleo, contratación o consultas ambientales generales no son
proyectos admitidos por este parser. No se ofrece histórico, inventario completo
de planeamiento, ni garantía de vigencia jurídica. Un tablón sin proyectos admitidos
provoca error y requiere revisión. La actualización vuelve a extraer la instantánea
completa; no interpreta ausencias como revocaciones o cancelaciones.

## Geometría y operación

`geometry_status: unavailable`. No hay geometría enlazada por expediente verificada;
no se transforma una referencia catastral en coordenadas ni se digitalizan planos.
Los PDFs pueden contener planos, pero este adaptador no comprueba una capa vectorial
ni un visor GIS para vincularla al expediente. `publication_ready: false`.
`schedule.enabled=false`, `geocode.jitter_missing=false`, `licencias.enabled=false`.

Requiere `requests`, BeautifulSoup (ya disponibles) y el ejecutable **pdftotext**
preinstalado en `/usr/bin/pdftotext`; no se instalaron paquetes ni se cambiaron
las dependencias. Si falta el ejecutable o cambia el PDF, la extracción falla.

## Validación reproducible

Runtime usado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_campillos -v
```

Cuatro pruebas pasan: agrupación/deduplicación y exclusiones, fechas y no inferencia
de aprobación, protocolo de paginación y rechazo de cambios, recorrido AJAX con
anuncio descubierto en la página posterior, carga del manifest y licencias vacías.
La extracción real se ejecutó con `load_portal_adapter(load_manifest('campillos'))`
y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, configurando únicamente
`capture_dir=evidence/live` para conservar las respuestas oficiales.

Evidencia local excluida de fuentes: `evidence/proyectos.jsonl`,
`evidence/validation.json`, capturas HTML/XML y ambos PDFs bajo `evidence/live/`.
El informe confirma `live_records=1`, `pages=2`, `inventory_documents=14`, URLs y
limitaciones. No se ha ejecutado publicación, sincronización, DB o despliegue.
