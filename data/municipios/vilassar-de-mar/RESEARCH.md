# Vilassar de Mar — INE 08219

Verificado 2026-11-07; código integrable con refresco deshabilitado.

## Fuente y registros

http://www.vilassardemar.cat/seu-electronica/serveis-municipals/linea-de-servei/planejament-urbanistic

HTTP 200 en extracción local. La variante HTTPS (con y sin www) falla la validación
de cadena de certificado (`unable to get local issuer certificate`), también en
curl. Se usa explícitamente la página HTTP pública; no se desactiva verificación
TLS ni se aplica fallback silencioso. Los documentos mantienen sus enlaces HTTPS
publicados. Conviene corregir cadena y pasar a HTTPS antes de activar producción.

Se extraen instrumentos concretos identificados como MPGOU o Pla especial urbanístic,
agrupando los documentos subordinados en un único expediente. Resultado directo:
**4 instrumentos, 0 licencias**: estacionamientos/aparcamientos, condiciones del
casco antiguo, usos de suelo no urbanizable y protección/catálogo de patrimonio.
No son enlaces genéricos a un buscador: todos tienen documentos PDF individualizados.
Las referencias mes/año quedan en el título, sin inventar día ni fecha de acuerdo.
La página no aporta descripciones de cada instrumento; no se copia el título como
descripción. El catálogo general PGOU, normativa genérica y formularios quedan fuera.

## Geometría / visor

geometry_status: unavailable (para registros extraídos; existe visor público)

La página enlaza un visor SIG real:
https://citymap.tecnogeows.com/user/100933209702821208923/map/45Kiq1sW5vGHTwjy6KBDkx
Se probó HTTP 200; devuelve una aplicación JavaScript Citymap/Tecnogeo, no geometrías
del expediente en el HTML. Enlaza además el MUC:
http://dtes.gencat.cat/muc-visor/AppJava/home.do?municipi=08219&set-locale=ca
No se verificó un endpoint vectorial ni un identificador que permita asociar las
cuatro modificaciones/planes a polígonos específicos. El centro de cámara del visor
no se utiliza como coordenadas de proyecto. Los planos PDF quedan como documentos.

## Validación

2 tests pasan: agrupación de varios documentos sin multiplicar proyectos, fechas
incompletas conservadas como tales, exclusión de trámites, fallo ante pérdida de
estructura. Extracción directa con timeout 25 s y archivos en
`/home/pablo/homes/artifacts/municipio-local-batches-20261107/vilassar-de-mar/`.
Sin orquestador, DB o publicación. `schedule.enabled: false`, licencias deshabilitadas
y `geocode.jitter_missing: false`. Pendiente geografía para controles de publicación.
