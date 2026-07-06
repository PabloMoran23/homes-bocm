# Ajalvir — investigación portal ayuntamiento

**Slug:** `ajalvir`  
**Nombre oficial:** Ajalvir (Villa de Ajalvir)  
**BOCM (referencia):** 20 anuncios  
**Fecha investigación:** 2026-07-06

## Dominios

| Rol | URL | Estado |
|-----|-----|--------|
| Web corporativa (Joomla + K2 + DOCman) | https://www.villadeajalvir.es | Accesible |
| Sede electrónica (Maggioli / eAdmin SPA) | https://ajalvir.eadministracion.es | Accesible (Angular; sin tablón scrapeable) |
| Sede legacy | https://sedeajalvir.eadministracion.es | No disponible (sesión caducada) |

## URLs base y páginas semilla

| Recurso | URL | Formato | Contenido |
|---------|-----|---------|-----------|
| Plan General (DOCman) | `/plan-general` | DOCman árbol | Avance PGOU: memoria, DIE, planos (~33 PDFs) |
| Transparencia PGOU | `/transparencia/plan-general` | DOCman | BOCM exposición avance + ZIP documentación |
| Tablón de anuncios | `/transparencia/tablon-de-anuncios` | DOCman tabla | PDFs varios (BOCM, ordenanzas, personal) |
| Solicitudes / licencias | `/transparencia/solicitudes` | DOCman | Impresos normalizados (obra mayor/menor, DR, actividades) |
| Urbanismo | `/areas-de-gobierno/urbanismo/pgou` | Joomla estático | Enlace a sección PGOU |
| Noticias urbanismo | `/noticias-y-actualidad-de-ajalvir/itemlist/category/169-urbanismo` | K2 | Convenios sectoriales, venta parcelas |
| Noticias plan general | `/noticias-y-actualidad-de-ajalvir/itemlist/category/255-plan-general` | K2 | Categoría planeamiento (vacía en muestra) |

## Estructura DOCman

Tablas `koowa_table` con enlaces:

```html
<a href="/plan-general/.../file" data-title="Bloque I. Memoria.pdf">...</a>
```

Carpetas navegables bajo `/plan-general/`:

- `bloque-i-memoria`
- `bloque-ii-die` (+ `anexos`)
- `bloque-iii-planos` → volúmenes 1–3 (planos de información, ordenación, infraestructuras)

## Proyectos / expedientes

- **Avance PGOU** (mar 2023): memoria, documento de impacto ambiental, 20+ planos PDF
- **Noticias K2**: resolución convenio urbanístico sector residencial 1, venta parcelas municipales SR1
- **Tablón**: algunos BOCM de ordenanzas; sin expedientes urbanísticos individuales con código

No hay listado de expedientes en información pública ni visor de seguimiento.

## Licencias de obra

No hay registro público de concesiones con coordenadas.

Fuentes:

- Impresos en `/transparencia/solicitudes` y `/Solicitudes/` (obra mayor, obra menor, declaración responsable, actividades)
- Presentación vía sede Maggioli (requiere identificación)

Estrategia adapter: filas informativas de trámites (como Pozuelo/Algete).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - No hay visor urbanístico municipal propio
  - Planos PGOU publicados como PDF sin georreferencia embebida
  - Sede Maggioli sin API GIS pública
  - Sin datos abiertos GeoJSON/WFS ni enlace ArcGIS
- **Estrategia:** el orquestador aplicará centroide municipal + jitter vía `geocode`
- **Limitaciones:** CMS Joomla solo PDFs; sede nueva no expone tablón HTML scrapeable; sin campo expediente→polígono

## Limitaciones generales

- Sede `ajalvir.eadministracion.es` migrada a SPA Angular; `/eAdmin/Tablon.do` devuelve shell sin datos
- Tablón DOCman en transparencia mezcla personal, tributos y BOCM genéricos
- Sin histórico tabular de licencias concedidas
- K2 noticias sin adjuntos PDF en artículos consultados

## Referencia adapters

- Joomla PDFs: `algete.py`
- DOCman `data-title`: patrón similar a `pinto.py`
- Trámites informativos licencias: `pozuelo.py`
