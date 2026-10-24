# Irun — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Web oficial | https://www.irun.org |
| CMS | Joomla (template `adiplantilla`) |
| Sede / documentos | `sac.irun.org/webservice_leer.aspx` (PDFs firmados) |
| Boletín provincial | BOG Gipuzkoa (`egoitza.gipuzkoa.eus/gao-bog/...`) |

## Fuentes — proyectos / planeamiento

| URL | Contenido |
|-----|-----------|
| `/es/urbanismo-vivienda/exposiciones-publicas/exposiciones-publicas-de-expedientes-urbanisticos` | Tabla de expedientes en tramitación / exposición pública (~20 filas visibles) |
| `/es/urbanismo-vivienda/planes-ordenacion-ejecucion-gestion/planeamiento-urbanistico-aprobado-definitivamente` | Planeamiento aprobado definitivamente (~20 filas) |
| `/es/obras/1414-{slug}?idob={id}` | Ficha de obra: estado, fechas BOG/DV, ámbito, instrumento, enlaces PDF (admin + técnica) |
| `/es/urbanismo-vivienda/planes-ordenacion-ejecucion-gestion/plan-general-de-ordenacion-urbana` | PGOU (documentación estática) |
| `/es/urbanismo-vivienda/informacion-territorial` | Información territorial (sin visor urbanístico enlazado) |

**Listado:** HTML `<table>` con enlaces `/es/obras/...?idob=`. Filtro opcional POST `idExpediente` en formulario de la página de exposiciones.

**Detalle:** tabla clave-valor (`Estado tramitación`, `Fecha de publicación B.O.G.`, `Instrumento`, `Ámbito`, etc.).

## Fuentes — licencias

| URL | Contenido |
|-----|-----------|
| `/es/urbanismo-vivienda` | Enlaces a trámites `?idt=` (licencias mayor/menor, comunicación previa, demolición, etc.) — páginas informativas |
| `/es/sede/tablon-de-edictos-y-anuncios/tablon-anuncios-digital` | Tablón digital por categorías (acordeón); filas con descripción + fechas + PDF SAC |

No hay listado tabular público de concesiones de licencia con dirección/coordenadas (patrón similar a Barakaldo: trámites + tablón cuando publican edictos).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - `https://geocallejero.irun.org` — callejero municipal (Spring SPA); sin capa de expedientes ni API WFS/ArcGIS enlazada al `idob`.
  - PMUS / información territorial en web — sin visor SIG con query por expediente.
  - Fichas de obra — solo PDF/ZIP (planos sin georreferencia automática en el adapter).
- **Estrategia:** centroide municipio en `manifest.portal.config.centroid` + jitter en geocode del orquestador.
- **Limitaciones:** planos en ZIP/PDF; ámbitos textuales (`ámbito 5.3.13 KORROKOITZ`) sin polígono descargable.

## Limitaciones generales

- User-Agent identificable recomendado (`poc-bocm-irun/1.0`); sin UA algunas peticiones pueden devolver 403.
- Listados de obras muestran ~20 entradas por página (sin paginación evidente en HTML estático).
- Tablón digital: títulos genéricos «Edicto» en PDF; descripción en columna de texto.
- Sin boletín municipal propio en pipeline (`bocm_count: 0`).
