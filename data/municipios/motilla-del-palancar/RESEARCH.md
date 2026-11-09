# Motilla del Palancar — INE 16134, Cuenca

Verificación en vivo: 2026-11-09. Comunidad autónoma: Castilla-La Mancha.

## Descubrimiento e inventario oficial

La página municipal https://www.motilla.com/urbanismo/ enlaza «Planeamiento» y
«Plan General de Ordenación Urbana» al mismo inventario:
https://www.motilla.com/documento-categoria/urbanismo-planeamiento/
Ambas páginas responden HTTP 200; capturas locales en `evidence/`.
También enlaza Publicaciones (`/category/urbanismo/`), Modelos
(`/modelos-urbanismo/`) y la sede https://motilladelpalancar.sedelectronica.es/.
Esas rutas no se presentan como inventarios de licencias concedidas ni se extraen.
Los modelos y solicitudes de licencia no prueban una concesión. No se usa prensa,
contratación, anuncios de licitación ni una noticia aislada como inventario.

El catálogo actual contiene 17 entradas con 153 enlaces PDF (153 URL distintas):
normas subsidiarias, modificaciones 1, 2, 3, 6 y 7, planes parciales de Cuevas
Frías SAU-1, SAU-3, SAU-4 y zona 1-16, PAU SAU 3-1 y SAU 3-2, cuatro estudios
de detalle y el PERI publicado bajo «URBANA CAMP DEL TURIA».
Se conserva exactamente la denominación municipal, incluso «ZONA 1-16»; no se
corrige por conjetura a otra zona. La numeración histórica llega a 16 y hay una
entrada adicional no numerada: no equivale a un registro histórico exhaustivo.

El adaptador lee todas las entradas y todos sus adjuntos directamente del HTML
del catálogo. Cada entrada municipal genera un instrumento, identificado por su
ID de contenido WordPress; memoria, planos, textos, anexos y boletines permanecen
en `documentos`, con URL de detalle e inventario como procedencia. Un ID de
contenido no se etiqueta como número de expediente administrativo.
Se inspeccionaron además los detalles de normas subsidiarias, zona 1-16 y PERI;
coinciden con la estructura documental visible en el catálogo. La extracción no
requiere solicitudes adicionales a esos detalles.

Se descargaron dos PDF de muestra: `Portada_PERI.pdf` confirma un Plan Especial
de Reforma Interior «Carretera de la Roda Nº1», Motilla del Palancar (Cuenca),
promovido por Urbana Camp del Turia. La portada menciona un acuerdo de pleno de
23-02-2007 y documentación de marzo de 2007; no se propaga ninguna de esas fechas
a la aprobación o publicación del instrumento. `DOCM-MOD2.pdf` tiene firma PDF
válida, pero no dio texto con pdftotext; no se afirma haber leído su acto.
Los restantes PDF se retienen como enlaces del inventario sin afirmar que se
haya descargado o validado individualmente su contenido.

## Semántica y límites

Las fechas incluidas en los títulos no explicitan su función. Se retiene el título
completo en `fecha_texto_origen`; `fecha`, `fecha_publicacion`, `fecha_acuerdo`,
`fecha_aprob` y `fase` quedan nulos. Fechas de directorios de subida y metadatos
web no se interpretan como aprobación ni publicación jurídica. Disponibilidad
actual no prueba vigencia legal, ejecución de obras ni aprobación definitiva.

Cobertura parcial: exclusivamente el catálogo publicado de planeamiento. No cubre
todas las obras físicas, expedientes nuevos, modificaciones no publicadas,
licencias ni toda la historia urbanística. Los documentos continúan agrupados
según el catálogo, sin afirmar que cada entrada sea un expediente administrativo
independiente o que los instrumentos sean todos simultáneamente vigentes.

No se observaron enlaces de paginación en el inventario actual. El adaptador
recorre los enlaces descubiertos de paginación de esa categoría, deduplica IDs
y URL y detecta conflictos. Destinos inesperados, entradas desconocidas, HTML
vacío, adjuntos ausentes o límites de tamaño/páginas provocan error antes de
reemplazar la salida. Los límites no se aplican como truncamiento silencioso.
Las actualizaciones refrescan una instantánea completa, no un histórico de bajas.

`geometry_status: unavailable`: se publican planos PDF, pero no se ha verificado
una capa vectorial vinculada a los instrumentos. No se vectorizan planos, no se
usan centroides y no se inventan coordenadas. `geometry`, `lat`, `lon` nulos;
`publication_ready: false`. Licencias, programación y jitter deshabilitados.

El clasificador compartido devuelve `adapter_incident / unknown_entity_spike`
para los 17 registros: su regla exige identidades administrativas o actos con
semántica adicional que este catálogo no ofrece. La extracción conserva esa
anotación y no inventa referencias de expediente para obtener elegibilidad. Son
instrumentos documentados reales, pendientes de revisión semántica independiente;
este trabajo no autoriza publicación ni declara aptitud para ingestión.

## Reproducción y evidencias

Runtime utilizado: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas (6 pasan):

```sh
/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_motilla_del_palancar -v
```

Cubren agrupación/deduplicación, procedencia, fechas desconocidas, tipos de
instrumento, exclusión de formularios/licitaciones, cambios de fuente, paginación
con ciclos, preservación de la salida ante error, carga del manifest y licencias
vacías. Extracción real ejecutada mediante `load_portal_adapter(load_manifest(
'motilla-del-palancar')).backfill_proyectos(Path('evidence/proyectos.jsonl'))`,
con `capture_dir` configurado localmente para guardar HTML.

`evidence/proyectos.jsonl`: 17 instrumentos; `evidence/validation.json`: recuentos,
URLs, comprobaciones HTTP, clasificación compartida y limitaciones. HTML, PDF y
texto de muestras guardados exclusivamente en `evidence/`, sin incluirlos como
fuentes para commit. Sin cambios compartidos, dependencias, DB ni despliegue.
