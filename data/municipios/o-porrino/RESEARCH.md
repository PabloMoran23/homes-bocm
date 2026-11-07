# O Porriño — INE 36039

Prueba 2026-11-07. Código para integración deshabilitada, alcance limitado al PXOM.

## Inventario municipal

- https://oporrino.org/ — HTTP 200; menú vigente descubre inventarios PXOM.
- https://oporrino.org/novas/urbanismo-comercio-e-industria/pxom-2003-planos-11000/ — HTTP 200.
- https://oporrino.org/novas/urbanismo-comercio-e-industria/pxom-2003-planos-15000/ — HTTP 200.

El adapter descubre enlaces del menú con denominación PXOM/año/PLANOS y lee sus
inventarios. Cada encabezado acredita el instrumento real, con documentos PDF
individuales. Agrupa escalas y hojas en **un instrumento**, no genera un proyecto
por plano ni por alias de URL. Las duplicaciones de menú responsive y de protocolo
se eliminan. El año se conserva en título/identificador; no se inventa fecha completa.
Si desaparecen los inventarios o sus documentos, falla sin producir un éxito vacío.
Límite explícito de 20 inventarios: superarlo causa error, no truncamiento silencioso.

Extracción directa: **1 proyecto PXOM 2003, 32 planos únicos, 0 licencias**.
No representa todos los proyectos, modificaciones posteriores ni concesiones del
municipio. No se usa la noticia de un proyecto aislado como inventario permanente.

## Geometría / visor

geometry_status: unavailable

El ayuntamiento enlaza el inventario de planeamiento de Xunta:
http://www.planeamentourbanistico.xunta.es/siotuga/inventario.php
Los inventarios municipales exponen planos PDF, no un WFS/GeoJSON o servicio
ArcGIS vinculado al instrumento. No se vectorizan PDFs ni se usan coordenadas
municipales como localización de proyecto. El enlace a Xunta no se publica como
proyecto adicional. Queda pendiente enriquecimiento cartográfico verificable.

## Validación

2 tests pasan: descubrimiento, deduplicación de inventarios/hojas y fallo ante
estructura o documentos ausentes. HTTP timeout 25 s por recurso y pausa 0,35 s.
Archivos de prueba y `validation.json` retenidos en
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/o-porrino/`.
`schedule.enabled: false`, `geocode.jitter_missing: false`, licencias deshabilitadas.
No se ejecutaron orquestador, DB, publicación ni cambios de cola. Pendiente geografía
para controles de publicación y ampliación de fuentes para cobertura más completa.
