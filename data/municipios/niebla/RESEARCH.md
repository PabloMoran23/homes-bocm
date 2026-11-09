# Niebla — Huelva — INE 21053

Investigación y extracción real: 9 de noviembre de 2026.

## Inventario oficial y alcance

Fuente municipal: https://www.niebla.es/es/descargas/

Se revisaron `municipio/manifest.py`, `municipio/adapters/portal.py`, el registro de
adaptadores y los ejemplos de Chipiona y Hernani antes de implementar este módulo.
El manifest declara Andalucía, Niebla (Huelva), código INE 21053 y desactiva
programación, licencias y desplazamientos artificiales de coordenadas.

La sección Descargas contiene el PGOU y formularios de licencias, además de
material de empleo y otras actividades. Se extraen exclusivamente las tres
familias documentales municipales verificadas: `PGOU_FIRMADO`, `PGOU_11_2023` y
`PGOU_APROBACION_PROVISIONAL_2024`. Los documentos ambientales, memorias,
planos, consultas y alegaciones se conservan como documentos del mismo
instrumento; no se convierten en proyectos independientes.

Resultado en vivo: **un instrumento, 120 enlaces PDF únicos**: 13 de la versión
inicial de 2023, 10 de los cambios de telecomunicaciones de 2023 y 97 del conjunto
etiquetado como aprobación provisional de 2024. Se retienen los títulos, sección,
ruta documental (incluido diligenciado/sin diligenciar), versión y páginas donde
aparece cada enlace. El identificador estable representa el PGOU, no una concesión.

## Paginación y procedencia

Las galerías comparten `pagedownloadgallery`. El HTML inicial contiene enlaces a
las páginas 2, 3 y última 5. El adaptador descubre todos los índices intermedios y
recorre las cinco páginas, incluyendo pestañas y acordeones inicialmente ocultos.
Las galerías pequeñas repiten documentos en varias páginas: se deduplican por URL
sin perder las páginas de procedencia. Cambios de familia documental, navegación
no soportada, respuestas vacías o una página activa distinta de la solicitada
provocan error antes de reemplazar el resultado. El límite de seguridad de 100
páginas provoca error explícito, nunca entrega un recorte silencioso.

Las cinco respuestas completas se capturan en `evidence/descargas-1.html` a
`descargas-5.html`; `validation.json` conserva sus hashes SHA-256. Se verificó una
muestra de cada familia mediante GET Range: tres respuestas HTTP 206,
`application/pdf`, firma `%PDF-`, 1024 bytes por muestra. No se descargaron ni
leyeron todos los PDF; conservar un enlace no certifica su contenido o accesibilidad
futura.

## Semántica y cobertura parcial

No se atribuyen fechas de acuerdo, aprobación o publicación. Los años de versiones,
nombres de archivos y fechas del CMS no se convierten en fechas administrativas.
Las etiquetas de aprobación proceden del inventario y no acreditan vigencia ni
aprobación definitiva. No se reconstruye una cronología legal a partir de ellas.
Como contraste de descubrimiento, el anuncio oficial
https://www.juntadeandalucia.es/boja/2023/213/95 remite a esta sección municipal;
no se incorpora como otro proyecto ni como fecha actual del instrumento.

No es un censo integral de obras públicas o de instrumentos históricos. No se
raspan noticias ni anuncios de contratación. Los formularios no prueban concesiones;
no se ha verificado un registro público utilizable de licencias concedidas y esa
extracción permanece desactivada. No hay coordenadas ni geometrías inferidas.
`publication_ready=false`. La anotación del registro común mantiene el instrumento
como `pendiente/insufficient_identity_evidence`: el catálogo documental no aporta
una referencia administrativa estructurada suficiente para habilitar actividad.
No se alteran las reglas compartidas para eludir esa revisión.

## Transporte y limitación TLS

Requests con sus certificados predeterminados y con
`/etc/ssl/certs/ca-certificates.crt`, y curl, fallaron por cadena de emisor no
verificable. HTTP redirige a HTTPS. El manifest configura expresamente
`tls_verify: false` para leer esta fuente pública; el adaptador mantiene verificación
por defecto si no se configura esta excepción y no silencia las advertencias.
La evidencia indica `tls_verified=false`: no se pudo autenticar criptográficamente
el servidor en este entorno. Esto limita la garantía de procedencia del transporte.

## Reproducción y pruebas

Runtime utilizado:
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

Pruebas: `-m unittest municipio.test_niebla -v`, ocho pruebas correctas de parser,
paginación, agrupación de versiones, pestañas ocultas, exclusiones, ausencia de
fechas/coordenadas inferidas, manifest, licencias desactivadas y conservación del
resultado anterior ante fallo de una página posterior.

Extracción real por `load_manifest('niebla')` y `load_portal_adapter(manifest)`,
seguida de `backfill_proyectos(Path('evidence/proyectos.jsonl'))`, configurando
`adapter.config['capture_dir']='evidence'`. `evidence/validation.json` contiene
`live_records=1`, los cinco `source_urls`, 120 documentos, resultados de muestras,
limitaciones y versión de la política de entidades. Las actualizaciones vuelven a
leer el inventario completo: no existe cursor temporal fiable. No se realizan
operaciones de base de datos, publicación, despliegue o geocodificación. La evidencia
es local y no forma parte de los cuatro archivos fuente entregados.
