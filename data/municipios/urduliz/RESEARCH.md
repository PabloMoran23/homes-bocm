# Urduliz — INE 48089, Bizkaia

Verificación directa: 2026-11-09. Un adaptador municipal, cobertura parcial de
instrumentos de planeamiento; no es un censo de obras ni de licencias concedidas.

## Descubrimiento y alcance

El [portal municipal](https://www.urduliz.eus/es-ES/Paginas/default.aspx) sirve
menús mediante SharePoint. Su API pública de lectura
`/es-ES/_api/web/lists/getbytitle('Menu Segundo Nivel')/items?$top=100`
enlaza Urbanismo y Exposición pública. La respuesta examinada no tiene `__next`.
No se necesita autenticación. La enumeración de subsitios devuelve 403; no se usa.

La [portada de Urbanismo](https://www.urduliz.eus/es-ES/Ayuntamiento/Urbanismo/Paginas/default.aspx)
enlaza estos inventarios utilizados por el scraper:

- [Planeamiento de desarrollo](https://www.urduliz.eus/es-ES/Ayuntamiento/Urbanismo/Paginas/planeamiento-desarrollo.aspx):
  actualmente un PEOU del centro de salud, parcela del sistema local de equipamiento
  asistencial de las Áreas 14 y 34. Se sigue su ficha descubierta, con memoria y
  16 planos: **un instrumento con 17 documentos**, no 17 actuaciones.
- [PGOU](https://www.urduliz.eus/es-ES/Ayuntamiento/Urbanismo/Paginas/PGOU.aspx):
  se recorren sus ramas de participación y documentación técnica, incluido el
  [avance](https://www.urduliz.eus/es-ES/Ayuntamiento/Urbanismo/Paginas/pgou-documentacion-tecnica-avance.aspx).
  **Un instrumento con 152 enlaces PDF**: 137 gráficos, 7 documentos escritos y
  8 enlaces desde participación. Hay copias publicadas en distintas carpetas;
  se conservan ambos enlaces si sus URL difieren, sin crear otro instrumento.

El inventario gráfico muestra inicialmente «Resultados 1 - 15 de 137». Se visitan
**las 10 páginas**, incluyendo las páginas 9 y 10 descubiertas durante el recorrido.
Se normaliza `?page=1`, se deduplican URL y se comprueba que los documentos únicos
del webpart coincidan con su total anunciado. Totales cambiantes, páginas ausentes,
consultas no reconocidas, documentos ausentes o límites de seguridad alcanzados
producen error antes de reemplazar el archivo de salida. No se limita al primer
grupo de enlaces visibles. El incremental refresca estas ramas completas; no
mantiene un historial de retiradas ni usa el estado como filtro temporal.

## Semántica y procedencia

Los registros tienen ID estable derivado de la URL de la ficha del instrumento.
Cada documento conserva título literal, URL y página municipal de procedencia.
Los campos `fecha_publicacion`, `fecha_acuerdo`, `fecha_aprob` y `fase` quedan nulos:
no se interpretan automáticamente fechas ni estados a partir de rótulos o nombres
de archivos. La página técnica presenta el avance, y la participación de agosto
de 2026 habla de continuar hacia aprobación inicial; no acredita aprobación
definitiva del PGOU ni concesión de ninguna licencia.

Se descargaron y examinaron tres PDF reales como contraste, sin incorporarlos
como tres registros adicionales:

- Memoria del PEOU: documento técnico de julio de 2024, con contenido específico
  del centro de salud. Su cabecera también contiene una referencia a AOD-01
  «Okin Zuri», aparentemente residual; se conserva como título del instrumento
  el publicado por el inventario municipal. No se deduce expediente de esa cabecera.
- Anuncio de exposición del avance: BOB número 90, **publicación 15-05-2026**,
  Decreto de Alcaldía 427/2026. El pie firma en Urduliz el 12 de mayo de 2026;
  esas fechas no son aprobación definitiva del plan.
- Certificado de inicio de formulación: acuerdo del pleno del **29-05-2025**;
  es inicio de formulación, no aprobación del PGOU. El adaptador conserva el enlace
  y su rótulo, pero no introduce esta fecha como aprobación del instrumento.

## Otras fuentes revisadas y exclusiones

La sección municipal de Normas Subsidiarias contiene el anuncio de 2000 y ocho
enlaces a modificaciones históricas. Convenio tiene documentos de 2014–2015 y
paginación. Ambas ramas quedan **fuera del alcance declarado**, al igual que el
archivo del BOB, la sociedad urbanística, el plan de movilidad y obras públicas.
No se presenta esta extracción como todo el planeamiento vigente de Urduliz.
La sección Exposición pública enlaza el buscador del BOB y otros documentos;
no se utiliza como registro de concesiones.

El [catálogo oficial de Bizkaia](https://www.opendatabizkaia.eus/es/organizacion/urduliz/catalogo/planeamiento-urbanistico-urduliz)
ofrece datos globales 2023–2026 y otras series; el JSON examinado contiene
estadísticas agregadas de suelo/vivienda. No se convierten en proyectos.
El portal `https://hapo.urduliz.eus/es/node/1360` describe el proceso participativo;
se prefiere el inventario documental del dominio municipal principal.
Formularios, contratos de servicios y anuncios de contratación no se ingieren.
`licencias.enabled=false`; los métodos de licencias escriben salida vacía deshabilitada.

## Geometría

`geometry_status: unavailable`. Se retienen planos PDF, pero no se vectorizan ni
se asignan coordenadas a los instrumentos. El visor foral
`https://appsec.ebizkaia.eus/O4GC000C/vistas/visor.xhtml` muestra capas de
planeamiento; no se ha verificado una capa vectorial vinculada a estos instrumentos.
`geometry`, `lat`, `lon` son nulos, `publication_ready=false` y
`geocode.jitter_missing=false`. No hay fechas o coordenadas fabricadas.

## Validación reproducible y evidencia local

Runtime: `/home/pablo/homes/artifacts/municipio-local-batches-20261107/venv/bin/python`.

`PYTHONDONTWRITEBYTECODE=1 <runtime> -m unittest municipio.test_urduliz -v`

Siete pruebas offline verifican manifest, agrupación, procedencia, fechas nulas,
identidad estable, paginación/deduplicación, rechazo de totales incompletos o
cambiantes y preservación de salida anterior ante error.

Extracción directa real con `UrdulizAyuntamientoAdapter('urduliz',
{'capture_dir': 'evidence/live'}, 'https://www.urduliz.eus')`, invocando
`backfill_proyectos(Path('evidence/proyectos.jsonl'))`: **2 registros reales**.
`evidence/validation.json` documenta conteo, URL recorridas y limitaciones.
`evidence/live/` contiene cada HTML y su URL original; `evidence/` también contiene
capturas de descubrimiento y tres PDF de contraste con sus textos extraídos.
La evidencia es local, excluida de los cuatro archivos fuente entregables.
Programación deshabilitada. Sin publicación, despliegue ni cambios compartidos.
