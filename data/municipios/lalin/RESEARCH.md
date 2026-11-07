# Lalín — INE 36024

Verificado 2026-11-07. Inventario municipal de instrumentos publicados, alcance limitado.

## Descubrimiento y evidencia

https://portaltransparencia.lalin.gal/web/es/portal-de-transparencia — HTTP200.
El apartado municipal Urbanismo enlaza genéricamente SIOTUGA y, separadamente, un
estudio de detalle concreto: urbanización Agro de Lalín de Arriba. El adapter
selecciona **instrumentos nombrados** del inventario municipal y sigue su publicación
oficial enlazada, sin rastrear ni volver a filtrar globalmente boletines regionales.
La URL individual no está fijada en código; se descubre desde la página municipal.
El enlace genérico a SIOTUGA no genera ningún registro.

Publicación individual descubierta y obtenida HTTP200:
https://www.xunta.gal/dog/Publicados/2016/20161010/AnuncioL224-210916-0002_es.html
Acredita Ayuntamiento de Lalín, aprobación inicial del estudio, expediente8592/16,
y publicación2016-10-10. Se conserva texto de procedencia y ambas URLs.
Resultado: **1 instrumento documentado, 0 licencias**. No se afirma que siga en
tramitación hoy ni que el inventario municipal contenga todo el planeamiento.
Los dos dominios principales `https://lalin.gal/` y `https://www.lalin.gal/` devolvieron
403; HTTP y robots muestran «Verificando navegador». El subdominio municipal de
transparencia sí es accesible; no se esquivó el desafío del sitio principal.

## Geometría / visor

geometry_status: unavailable

El portal municipal enlaza
http://www.planeamentourbanistico.xunta.es/siotuga/inventario
No se verificó geometría vectorial ligada a este estudio de detalle. El anuncio
descargado tiene texto legal, no coordenadas o polígono. No se fabrica localización
ni se usa un límite municipal como geometría del proyecto.

## Validación

2 pruebas pasan: instrumento nombrado frente a enlace genérico y rechazo de
anuncio de otro municipio. Fecha de publicación tomada del encabezado DOG, no de
la fecha de subida del portal. Live HTTP timeout25s, pausa0,35s, artefactos en
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/lalin/`.
`schedule.enabled: false`, licencias deshabilitadas, `geocode.jitter_missing: false`.
Sin DB/orquestador/publicación/cola. Falta geografía para publicar.
