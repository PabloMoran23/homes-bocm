# Camariñas — INE 15016, A Coruña, Galicia

Verificación en vivo: 2026-11-09. Adaptador municipal único, cobertura parcial de
instrumentos de planeamiento. No es un registro de licencias concedidas ni un
inventario completo de obras públicas. Se revisaron previamente `manifest.py`,
`adapters/portal.py`, `registry.py` y los ejemplos Hernani y Manlleu.

## Inventario oficial y descubrimiento

Punto de entrada actual de Urbanismo:
https://camarinas.net/portal-cidadan/presentacion-urbanismo/gl

Su navegación enlaza tres instrumentos, descubiertos en cada ejecución:

- PXOM: https://camarinas.net/pxom/PXOM_CAMARINHAS.htm
- Modificación puntual: https://camarinas.net/portal-cidadan/modificacionpuntualpxom/gl
- PEPRI: https://camarinas.net/pepri/pepriCAMARINHAS.htm

Los sitios documentales antiguos de PXOM y PEPRI utilizan frames. Sus índices son
`/pxom/PXOM_CAMARINHAS_indice.html` y `/pepri/pepriCAMARINHAS_indice.html`.
Se siguen todos los índices HTML anidados, incluidos frames y mapas de imagen
`area[href]`, con deduplicación de páginas y PDF. Las fichas de núcleos, ámbitos,
manzanas, catálogos y planos forman parte de su instrumento: no generan proyectos
separados. Se retiene `url_indice` en cada documento y `paginas_fuente` en cada
registro. Se excluye la ayuda del visor (`axuda`), que no es documentación del plan.

El enlace antiguo municipal usa `http://www.camarinas.net`; el equivalente probado
es `https://camarinas.net`, con validación TLS activa. El hostname `www` en HTTPS
presentó un certificado no válido para ese nombre; no se deshabilita TLS.

La modificación se extrae exclusivamente del contenedor de descargas de contenido,
no del menú ni del pie de página. Su documento es:
https://camarinas.net/media/documentos/Mod_Pxom.pdf
Los dos enlaces «título» y «Descargar» corresponden al mismo documento y se agrupan.
El PDF del registro de actividades de tratamiento del pie de página queda excluido.

## Resultado y semántica documental

La extracción real produce **3 registros**: PXOM (251 PDF enlazados), modificación
puntual (1 PDF) y PEPRI (630 PDF). Son **882 enlaces documentales**, no 882 proyectos.
Los títulos PXOM/PEPRI se contextualizan con el municipio. IDs estables por instrumento.
Las URL, títulos documentales y procedencia se extraen de los índices oficiales.
No se consulta actualidad, contratación ni formularios para producir registros.

Muestra de documentos descargados y comprobados HTTP 200 y firma `%PDF-`:

- PXOM: https://camarinas.net/pxom/Memorias/M_Ordenacion/Tomo_II/Normativa_Urbanistica.pdf
- PEPRI: https://camarinas.net/pepri/Memorias/Ordenacion/TomoIII/01_NORMATIVA/15016_PEPRI_202112_AP_NU_signed.pdf
- Modificación: https://camarinas.net/media/documentos/Mod_Pxom.pdf

La portada del PXOM dice documento **para** aprobación definitiva, octubre de 2012:
la edición no equivale a un acuerdo de aprobación. La presentación PEPRI indica
edición de mayo de 2022; la normativa descargada contiene una diligencia de aprobación
plenaria de 27 de mayo de 2022, aunque el encabezado interior conserva el texto de
aprobación provisional. No se interpreta el sufijo de fichero `202112_AP` como fecha
de aprobación. La copia del BOP de la modificación nº 1 corresponde al 31 de agosto
de 2022, nº 165, anuncio 2022/5314, y relata la aprobación por orden de 20 de julio
de 2022 y su publicación DOG de 17 de agosto de 2022. Son acontecimientos distintos.

Estas observaciones son investigación manual de PDF. El adaptador analiza los índices
HTML y no implementa extracción del texto de PDF: deja `fecha`, `fecha_publicacion`,
`fecha_acuerdo` y `fecha_aprob` en null y no asigna fase ni vigencia. Tampoco usa fechas
del servidor HTTP como fechas jurídicas. Los PDF enlazados se marcan
`contenido_verificado: false` porque no se descarga y verifica cada uno en cada ejecución.
La muestra manual no acredita disponibilidad ni contenido de los 882 enlaces.

## Límites, paginación y geometría

Los índices examinados no muestran paginación de resultados; son una biblioteca
jerárquica, recorrida completamente. Los ciclos se deduplican; 200 páginas HTML por
instrumento es un límite de fallo explícito, nunca un corte que entregue éxito.
Un enlace de paginación reconocible, un contenedor perdido, inventario incompleto,
error de red o instrumento sin documentos provoca fallo antes de reemplazar la salida.
Una actualización vuelve a recorrer el inventario completo y reemplaza atómicamente
el JSONL. No se usa el fichero de estado para omitir instrumentos.

No se ha verificado un registro público de licencias concedidas: los trámites de la
sede enlazados por Urbanismo son solicitudes y no se extraen como concesiones.
`licencias.enabled=false`, `schedule.enabled=false`, `geocode.jitter_missing=false`.

`geometry_status: unavailable`. Los índices ofrecen planos PDF, no geometría
vectorial vinculada a los registros. No se vectorizan planos, geocodifican topónimos,
usan centroides ni inventan coordenadas. `lat`, `lon`, `geometry` son null y
`publication_ready=false`. No se ha probado una integración cartográfica municipal.
La política compartida del registro clasifica estos registros genéricos como
`pendiente / insufficient_identity_evidence`; esto no es aprobación de publicación.

## Validación reproducible y evidencias locales

Runtime preinstalado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `python -m unittest municipio.test_camarinas -v` — 7 pruebas pasan:
manifest/carga del registro, descubrimiento y exclusión de formularios, URL y mapas
de imagen, frames anidados/ciclos/deduplicación/procedencia/fechas no inferidas,
rechazo de paginación y pérdida de documentos, snapshot completo y licencias
vacías, y conservación de la salida anterior ante fallo de red. El caso completo
verifica también la exclusión del PDF de privacidad del pie.

Extracción real mediante `load_manifest` y `load_portal_adapter`, ejecutando
`backfill_proyectos`, con capturas HTML activadas. Artefactos locales en `evidence/`:
`proyectos.jsonl`, `validation.json` (recuento, URL, límites, resultado de política),
`sources/<sha256(url)[:20]>.html`, muestras PDF y texto, y `run_live.py` para reproducir
la ejecución con `PYTHONPATH=.`. No se publican ni se incluyen estas evidencias en
los cuatro archivos fuente. No se han modificado dependencias ni módulos compartidos.
