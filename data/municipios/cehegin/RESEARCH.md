# Cehegín (Murcia), INE 30017

Investigación y extracción en vivo: 7 de noviembre de 2026. Adaptador único
`municipio.adapters.cehegin:CeheginAyuntamientoAdapter`.

## Fuentes oficiales descubiertas

- [Índice municipal de transparencia](https://transparencia.cehegin.es/t/categorias?a=98): identifica las secciones de Urbanismo y Obras y enlaza el PGOU municipal.
- [Modificación de las obras más importantes](https://transparencia.cehegin.es/p/182-modificacion-de-las-obras-mas-importantes): inventario utilizado. Dos enlaces repetidos apuntan a un mismo XLSX de proyectos y un tercero a otro XLSX de obras superiores a 500.000 euros. Se deduplican por URL y se descargan ambos documentos actuales enlazados, sin fijar sus nombres en el código.
- [PROYECTOS DE OBRA.xlsx](https://transparencia.cehegin.es/storage/uploads/1652794547PROYECTOS%20DE%20OBRA.xlsx): cuatro obras reales, con nombre, inicio, fin, presupuesto de adjudicación y empresa constructora. No es un listado de anuncios de licitación.
- [Obras más 500000.xlsx](https://transparencia.cehegin.es/storage/uploads/1652794628Obras%20m%C3%A1s%20500000.xlsx): una obra, Pabellón de deportes, Fase 1 y Fase 2; incluye fecha de inicio, plazo y presupuesto de adjudicación.
- [Obras en curso](https://transparencia.cehegin.es/p/177-obras-en-curso): solo instrucciones y enlace al perfil de contratación; no se transforma en una obra sintética.
- [Convenios Urbanísticos](https://transparencia.cehegin.es/p/180-convenios-urbanisticos): enlace al Convenio Argostalia firmado, anexo y adenda; no extraído como obra física.
- [Normativa urbanística](https://transparencia.cehegin.es/p/181-normativa-vigente-en-materia-de-gestion-urbanistica): PDF de normativa y ordenanzas del documento refundido de 2021; fuera del inventario de obras.
- [Urbanismo](https://cehegin.es/noticias/urbanismo/) y [Plan de ordenación Urbana 2021](https://cehegin.es/plan-de-ordenacion-urbana-2021/): localizados mediante búsqueda web oficial. El cliente HTTP local recibió desconexiones en cehegin.es y HTTP 520 en www.cehegin.es. El lector web muestra una página PGOU que requiere JavaScript. No se inventa un registro del plan ni se presenta esta extracción como cobertura del planeamiento.
- El portal `https://cehegin.governalia.es/` responde con taxonomías y enlaces JavaScript. No forma parte del inventario implementado.

## Cobertura y significado

Resultado: **5 registros de obras físicas**, extraídos de dos documentos XLSX oficiales
servidos con HTTP 200. Las cuatro actuaciones de urbanización son P.A.14,
P.A.3 de Valentín, Traseras de la Tercia y P.A.8; el quinto registro agrupa
las fases 1 y 2 del pabellón tal como aparecen en una sola fila de origen.
Se conserva la grafía original, incluido `MODIFICIADO`.

La ficha muestra `17-05-2022 13:37:31` como última actualización de la sección.
Es un inventario documental accesible actualmente con información histórica,
no una garantía del estado actual de ejecución ni un censo completo municipal.
Las fechas de inicio encontradas van de 2009 a 2019. No se establece fase actual.

`fecha_inicio` y `fecha_fin` se derivan exclusivamente de las columnas de esos
nombres, usando la época Excel declarada por el libro. Un fin vacío se omite;
el plazo `8.25 meses` se conserva sin calcular un fin. La actualización de la
sección no se interpreta como publicación, acuerdo o aprobación. No hay campos
`fecha`, `fecha_publicacion`, `fecha_acuerdo` ni `fecha_aprob` inferidos.
Los presupuestos y contratistas permanecen en `campos_originales` con la
procedencia exacta; no se reinterpretan como costes ejecutados.

Cada documento conserva URL, nombre, hoja, fila y campos originales.
Las filas del mismo nombre normalizado se agrupan reteniendo todos sus documentos;
las discrepancias de fecha o plazo provocan error. Los identificadores dependen
del nombre de la obra, no del índice de fila o del enlace temporal.
No hay coordenadas: el mapa del pie de página sitúa el Ayuntamiento, no las obras.
`publication_ready=false`, `geometry_status=unavailable`.

No se observaron controles de paginación en esta ficha. Se detecta paginación
explícita y se falla para evitar cobertura silenciosamente incompleta. Se recorren
todos los enlaces XLSX de las tablas y todas las hojas y filas declaradas en cada
libro, incluidas hojas vacías. No se aplica límite de páginas, filas ni registros.
Un cambio de esquema, ausencia de inventario o libro sin obras produce error
antes de sustituir el JSONL anterior. Incremental significa refresco completo
del inventario actual; no modifica el estado incremental recibido.

Licencias desactivadas: no se ha verificado un registro público de concesiones.
Formularios de solicitud, normativa y anuncios de contratación no se usan como
licencias ni como proyectos. Programación y jitter geográfico desactivados.

## Validación reproducible

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.
Sin instalaciones ni cambios compartidos.

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_cehegin -v
```

Cinco pruebas correctas: manifest; deduplicación de enlaces, exclusión de formularios
y rechazo de paginación/orígenes extraños; recorrido de múltiples hojas y agrupación
de documentos; semántica de fechas/plazos; rechazo de esquemas vacíos, desconocidos
y conflictos. La extracción real también verifica el formato de cadenas compartidas
que emplean los dos libros municipales, sin dependencias XLSX adicionales.

La ejecución real cargó el manifest con `load_manifest('cehegin')`, resolvió el
adaptador con `load_portal_adapter`, configuró `evidence_dir` local y llamó a
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`. Resultado: cinco registros;
la política compartida los anota como categoría desconocida (5/5), sin impedir la
extracción ni inventar una categoría de edificio.

Evidencia local no destinada a commit:
`evidence/proyectos.jsonl`, `evidence/validation.json`, `evidence/inventory.html`,
`evidence/works-0.xlsx`, `evidence/works-1.xlsx` y capturas de descubrimiento.
La validación incluye URLs, recuento real y limitaciones. Sin base de datos,
publicación, geocodificación ni despliegue.
