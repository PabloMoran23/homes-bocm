# Abarán — INE 30002, Murcia

Verificado el 2026-11-07 con el runtime preinstalado. Identidad: Ayuntamiento de
Abarán, provincia y comunidad autónoma de Murcia. Sin ejecución programada,
licencias deshabilitadas y sin desplazamiento artificial de coordenadas.

## Descubrimiento y fuente actual

La portada oficial https://abaran.es/ enlaza «Plan General». El inventario de
transparencia https://abaran.es/transparencia/informacion-en-materia-de-ordenacion-del-territorio-y-medio-ambiente/
enlaza el mismo destino mediante «Instrumentos de ordenación del territorio y
planes urbanísticos»:

https://abaran.es/plan-general-municipal-de-ordenacion-de-abaran/

Es un inventario documental municipal real, no una noticia ni un formulario de
solicitud. Se captura su HTML completo, se recorren todos los enlaces documentales
de su contenedor y se conservan PDF y ZIP. No hay paginación en la fuente revisada;
si aparece, el adaptador falla explícitamente, sin aceptar una página incompleta.
También rechaza secciones nuevas, enlaces documentales desconocidos, contenido
vacío, redirecciones inesperadas y documentos de modificaciones sin número.

## Resultado y procedencia

La extracción en vivo mediante el adaptador cargado por el manifest devuelve
**4 instrumentos y 31 enlaces documentales únicos**:

- PGMO: 25 documentos (catálogo, memoria, normas y planos de distintas escalas).
- Modificación 24: publicación BORM y planos, 2 documentos.
- Modificación 25: dos partes ZIP y publicación BORM, 3 documentos.
- Modificación 28: un PDF, 1 documento.

Los botones «Descarga» repetidos no generan documentos duplicados. Cada documento
retiene título, URL íntegra y página de procedencia; cada instrumento retiene
ID estable, municipio, INE, tipo y URL real del inventario. Los IDs dependen del
instrumento, no del año de subida del archivo. Las modificaciones nuevas numeradas
se agrupan dinámicamente; no se fija una lista de cuatro resultados en el código.

Se descargaron y verificaron como PDF los tres documentos de modificaciones
PUBLICACION-BORM-APROBACION-DEFINITIVA-24.pdf,
BORM-13-17-de-enero-de-2014-modif-25.pdf y MODIFICACION-N28-USOS.pdf.
Las capturas, hashes y textos extraídos están en `evidence/`. Los ZIP y los demás
PDF se conservan como enlaces del inventario, sin inspeccionar todos sus contenidos.

## Fechas y límites

No se emiten fechas de publicación, acuerdo o aprobación: el inventario no las
expone como campos separados. Las rutas `/2026/02/` son fechas de subida, no de
aprobación. Como comprobación de esta distinción, el PDF de la modificación 24
contiene publicación BORM de 2012-10-02 y acuerdo plenario de 2012-09-13; el de la
25 contiene publicación BORM de 2014-01-17 y una orden de 2013-11-26. Estos datos
no se convierten en campos mediante valores manuales ni se confunden entre sí.
El PDF de la modificación 28 no ofrece texto extraíble con pdftotext.

La cobertura es **parcial**: inventario publicado del PGMO, no registro exhaustivo
de expedientes urbanísticos, modificaciones históricas, obras ni licencias
concedidas. No se certifica vigencia jurídica consolidada de cada documento ni
estado de ejecución material. Las licencias no se extraen de formularios o anuncios.
El método update refresca la instantánea completa; no escribe un cursor temporal
ni elimina expedientes en sistemas externos. No se ha verificado geometría
vectorial asociada a los instrumentos. Los planos PDF no se convierten en puntos:
`geometry_status: unavailable`, `publication_ready: false`, sin coordenadas.

## Validación reproducible

Desde la raíz del repositorio:

```sh
PYTHONDONTWRITEBYTECODE=1 /home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python -m unittest municipio.test_abaran -v
```

Cuatro pruebas verifican agrupación y deduplicación, procedencia, ausencia de
fechas/coordenadas inferidas, estabilidad de IDs, fallos de paginación y cambios de
formato, contrato HTTP, actualización, licencias deshabilitadas y manifest.
La extracción real usa `load_portal_adapter(load_manifest('abaran'))` y
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`, con captura local opcional
`adapter.config['capture_dir'] = 'evidence'`. El wrapper de política compartido se
ejecutó: anotó los cuatro instrumentos con categoría desconocida; no se altera esa
política ni se atribuye una categoría inmobiliaria a instrumentos de planeamiento.
El recuento, URLs y límites quedan en `evidence/validation.json`.

Durante el trabajo hubo un fallo transitorio ENOSPC. La implementación se preparó
en `/tmp`, se trasladó al workspace cuando volvió a admitir escrituras y se
validó allí. No se modificaron dependencias, archivos compartidos, Git ni servicios
externos. La evidencia es local y no debe incluirse en un commit.
