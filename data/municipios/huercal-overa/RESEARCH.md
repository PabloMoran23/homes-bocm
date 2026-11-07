# Huércal-Overa — INE 04053

Verificado 2026-11-07. Código deshabilitado, alcance consultas públicas de planeamiento.

## Fuentes y extracción

Inventario municipal de participación (HTTP 200):
https://www.huercal-overa.es/Servicios/cmsdipro/index.nsf/informacion.xsp?documentId=9DF06E8926783D90C12581300029329D&p=huercal-overa

Se descubren las consultas de PGOU, estudios de detalle y planes de reforma interior,
excluyendo ordenanzas fiscales y trámites. Cada detalle se descarga realmente desde
huercal-overa.es o el alojamiento provincial dipalme.org y se verifica su encabezado,
documentos adjuntos o contenido descriptivo suficiente. Hay 8 consultas y **7
instrumentos**, agrupando los dos anuncios de innovación 23 por su número explícito.
Otros expedientes: PRI AT-9 La Atalaya, innovaciones 22,25,19,21 y estudio de detalle
El Saltador. No se inventan fechas completas ni coordenadas; las descripciones son
texto fuente, nunca una repetición fabricada del título. Los enlaces de documentos
excluyen política de calidad del encabezado/pie de página al limitarse al formulario
de contenido. El inventario es una página sin paginación; >40 consultas provoca error.

El tablón general también está disponible, pero pagina mediante XPages y queda fuera
del alcance: https://www.huercal-overa.es/Servicios/cmsdipro/index.nsf/tablon_view_entidad_rol.xsp?p=huercal-overa
No se afirma haber extraído su histórico completo. Ninguna licencia se acredita por
el inventario seleccionado: licencias deshabilitadas, salida vacía.

## Geometría / visor

geometry_status: unavailable (para estos instrumentos)

Se investigaron enlaces municipales de planeamiento, documentos de consultas y la
referencia provincial de visor GIS de Diputación de Almería. Los detalles extraídos
exponen documentos de avance/ambientales en PDF, sin geometría vectorial enlazada a
estos expedientes. No se ha establecido correspondencia con capas del visor provincial
ni vectorizado PDFs. La cartografía publicada no se sustituye con centroide municipal.

## Prueba y límites

Extracción HTTP directa limitada a 25 s por recurso y pausa 0,35 s: 7 proyectos,
0 licencias. Dos pruebas pasan (selección de consultas, identidad de innovación,
exclusión de adjuntos globales, fallo de contenido ausente). Static check válido.
Archivos conservados en `/home/pablo/homes/artifacts/municipio-local-batches-20261107/huercal-overa/`.
`schedule.enabled: false`, `geocode.jitter_missing: false`. Sin DB, publicación,
orquestador ni cambios de cola. Pendiente geometría para validación de publicación.
