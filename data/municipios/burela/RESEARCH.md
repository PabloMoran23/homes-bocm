# Burela — Lugo — INE 27902

Verificado mediante HTTP en vivo el 2026-11-07. Adaptador:
`municipio.adapters.burela:BurelaAyuntamientoAdapter`.

## Inventario oficial y descubrimiento

La página municipal [Urbanismo](https://burela.org/es/urbanismo) contiene una
biblioteca de planeamiento, además de información sobre servicios y trámites.
Se descubren sus enlaces en cada ejecución; no se usa una noticia aislada como
semilla ni se interpreta la oferta de servicios como licencias concedidas.

- «Documento de Aprobación Definitiva» enlaza `/gl/node/68`, que redirige a
  https://burela.org/gl/pxom-documento-de-aprobacion-definitiva.
- «Aprobación Inicial de la Modificación Puntual del Plan General de Ordenación
  Municipal (PXOM)» enlaza `/es/node/999`, que redirige a
  https://burela.org/es/aprobacion-inicial-de-la-modificacion-puntual-del-plan-general-de-ordenacion-municipal-pxom.

También se comprobó https://burela.org/PXOM/index.htm, biblioteca antigua del mismo
PXOM. No se añade como otro proyecto: duplicaría el instrumento publicado en la
web actual. Las capturas de descubrimiento y las de la ejecución están en evidence/.

## Registros y fechas

Extracción real: **2 instrumentos**, con **146 PDF únicos** del PXOM y **10 ZIP**
de documentación de la modificación. Memorias, planos, normas y anexos se agrupan
en `documentos`, manteniendo los enlaces, etiquetas y página de procedencia. La
biblioteca del PXOM contiene enlaces duplicados de texto/icono y fragmentos de
etiquetas mal maquetados: se deduplican por URL y se conservan todas las etiquetas
no vacías, sin inventar títulos. Los identificadores locales son estables por
instrumento, no supuestos números de expediente administrativo.

El texto oficial del PXOM identifica la Orden de aprobación definitiva de
**2014-03-31**, su publicación en DOG de **2014-04-02** y la publicación de normas
en BOP de **2014-04-14**. Se guardan respectivamente en `fecha_aprob`,
`fecha_publicacion` y `fecha_publicacion_normativa`. No son fechas de publicación
de la página web ni concesiones de licencia. `fecha_acuerdo` y la fecha genérica
quedan vacías. La modificación sólo acredita documentación correspondiente a
aprobación inicial e información pública; sus fechas quedan vacías. El nombre de
carpeta PXOM22 no se convierte en fecha. Su fase es la descrita por esta biblioteca,
no una certificación independiente de que siga siendo la última fase tramitada.

Se conservan los enlaces originales de documentos y se normalizan a HTTPS y al
host burela.org para consulta, codificando espacios/caracteres. Se comprobó con
HTTP Range el PDF de normas y el ZIP 01.MX: ambos HTTP 206, cabeceras y firmas
PDF/ZIP correctas, capturas parciales de 4096 bytes. No se han descargado o validado
íntegramente los 156 documentos ni extraído el interior de los ZIP.

## Cobertura, paginación y geometría

Cobertura parcial de planeamiento publicado en la sección actual de Urbanismo;
no constituye un censo de obras, sectores ejecutados, modificaciones históricas
ni licencias. No se convierten en proyectos las noticias, anuncios de contratación
o formularios. Licencias deshabilitadas por ausencia de registro verificado.

Las páginas examinadas no tienen paginación. El extractor rechaza paginadores o
enlaces siguientes, ausencia de cualquiera de las dos entradas, instrumentos
adicionales ambiguos, pérdida del artículo, documentos o narrativa requerida.
No hay límite de documentos ni recorte de resultados. Una ampliación del inventario
requiere revisar agrupaciones; falla en lugar de aceptar una cobertura truncada.
Las actualizaciones vuelven a leer la biblioteca completa, sin usar fechas para
omitir documentos; un fallo de descarga o de análisis conserva la salida previa.

`geometry_status: unavailable`. Estas páginas proporcionan planos en PDF/ZIP,
sin geometrías vectoriales asociadas a un identificador de instrumento. No se ha
comprobado un servicio SIG enlazable a estos registros ni georreferenciado planos.
Coordenadas y geometría vacías, `publication_ready: false`. El guard compartido de
entidades clasifica los dos registros como `unknown` (no se inventan referencias
administrativas para forzar su elegibilidad); se conserva su anotación en evidencia.

## Validación reproducible

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_burela -v
```

6 pruebas: descubrimiento excluyendo formularios, agrupación y deduplicación,
fechas diferenciadas, fechas ausentes, rechazo de paginación/cambios de fuente,
conservación de salida ante fallo y resolución del manifest/licencias vacías.
Extracción en vivo realizada mediante `load_manifest('burela')`,
`load_portal_adapter(manifest)` y `backfill_proyectos(Path('evidence/proyectos.jsonl'))`,
con `portal.config.capture_dir='evidence/sources'` sólo en esa ejecución local.
`evidence/validation.json` registra recuentos, URLs consultadas, limitaciones,
anotación de entidades y comprobaciones documentales. Las evidencias son locales,
no forman parte de los cuatro archivos fuente.

`schedule.enabled=false`, `geocode.jitter_missing=false`, `licencias.enabled=false`.
Sin cambios compartidos, dependencias, base de datos ni publicación.
