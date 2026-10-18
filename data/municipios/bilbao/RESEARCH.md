# Bilbao — portal ayuntamiento (urbanismo)

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web / sede | https://www.bilbao.eus |
| Open Data catálogo | https://www.bilbao.eus/opendata/es/catalogo |
| Contratos de obras (JSON) | https://www.bilbao.eus/opendata/datos/licitaciones?formato=json&tipoContrato=obras&idioma=es |
| Convenios por año (JSON) | `https://www.bilbao.eus/cs/Satellite?c=Page&language=es&pageid=1272976790212&pagename=Bilbaonet/Page/OD_ListadoConvenios&anio={AÑO}&formato=JSON` |
| RSS noticias Urbanismo y Vivienda | https://www.bilbao.eus/cs/Satellite?language=es&pageid=3000075248&pagename=Bilbaonet/Page/BIO_suscripcionRSS&tipoSus=Noticias&idSec=3000003788 |
| Trámites licencias obras mayores | https://www.bilbao.eus/cs/Satellite?anclaServ=aB3&c=BIO_Procedimiento_FA&categoria=municipales&language=es&pageid=1279126910314&pagename=Bilbaonet%2FBIO_Procedimiento_FA%2FBIO_ProcResumen&perfil=ciudadano&rutaCatServ=3002269359%2C1279189514568 |
| Transparencia urbanismo (planes, convenios) | https://www.bilbao.eus/cs/Satellite/transparencia/es/ambitos/urbanismo-obras-y-medio-ambiente/urbanismo |
| GeoBilbao (visor municipal) | https://www.geobilbao.eus/ |

## Cómo se listan expedientes / planeamiento

- **No hay** listado público machine-readable de expedientes de planeamiento en trámite (consulta presencial / solicitud escrita).
- **Open Data — licitaciones**: API JSON por año con `Objeto`, `N_Expediente`, `Fecha_de_adjudicacion`; filtramos filas con texto urbanístico (PGOU, ordenación, urbanización, área de Planificación Urbana, etc.).
- **Open Data — convenios**: JSON anual con `titulo`, `tipoconvenio`, `fechaaprobacion`, `numeroexpediente`; convenios urbanísticos identificables por título/tipo.
- **RSS**: noticias del Gabinete de Prensa (sección Urbanismo y Vivienda, `idSec=3000003788`).
- **Transparencia**: enlaces a PGOU 2022, inventario de figuras y convenios; en el entorno del agente algunas rutas `/transparencia/` devuelven **403** o redirección a mantenimiento — los datasets Open Data son más estables.

## Licencias de obra

- Trámites descritos en la sede (obras mayores/menores, comunicaciones); **no** hay dataset de licencias concedidas con dirección/coords.
- El adapter registra páginas informativas de trámites (patrón Pozuelo).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Diputación Foral de Bizkaia — ArcGIS MapServer `PX_Bilbao_Metropolitano_inf` (capas de planeamiento municipal, p. ej. suelo residencial 119–122, planeamiento suspendido 134).
  - Query REST: `.../MapServer/{layer}/query?returnGeometry=true&outSR=4326&f=geojson`
  - GeoBilbao: visor orientativo; sin enlace directo expediente → polígono en el adapter.
- **Estrategia:** tras obtener el título del proyecto, buscar tokens toponímicos en `ETIQUETA` / `DESCRIPCION` de las capas PGOU; muchas parcelas carecen de etiqueta textual → enriquecimiento esporádico.
- **Limitaciones:** sin visor de expediente urbanístico enlazado; transparencia a veces bloqueada; coordenadas de licencias no publicadas; PGOU en EPSG:25830 en origen (se solicita `outSR=4326`).

## Limitaciones generales

- APIs Satellite lentas (504 intermitente en convenios años antiguos).
- CMS Oracle WebCenter (Satellite); scraping HTML limitado.
- Sin boletín regional asociado en cola (`bocm_count: 0`).
