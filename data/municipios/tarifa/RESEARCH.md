# Tarifa — investigación portal ayuntamiento

Municipio: **Tarifa** (`tarifa`) — Cádiz, Andalucía  
BOCM/BOJA: `boja` (2 entradas en CSV histórico)

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.aytotarifa.com |
| Sede electrónica (eConstruye/Absis) | https://sede.aytotarifa.com |
| Tablón de edictos | https://sede.aytotarifa.com/sede/castellano/Externos/ASP/enlacesPortada/EnlacesPortadaSede.asp?enlacePortada=tablon |
| PGOU / planeamiento | https://www.aytotarifa.com/pgou/ |
| Avisos urbanismo (WP) | https://www.aytotarifa.com/notice-category/urbanismo-informacion-publica/ |
| Oficina técnica (calificación ambiental) | https://www.aytotarifa.com/notice-category/oficina-tecnica/ |
| Trámites licencias (informativo) | https://www.aytotarifa.com/atencionalaciudadania/informacion-citaprevia/ |
| SITUA Junta de Andalucía | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf |

## Cómo se listan expedientes

### WordPress TownPress (`lsvr_notice`)

- Categorías taxonómicas `notice-category/*` con avisos de información pública, edictos y documentación técnica (PDFs enlazados en cada aviso).
- RSS por categoría (`/feed/`) y archivos paginados (`/page/N/`).
- Títulos completos en `<h1>` de cada aviso bajo `/notices/<slug>/`.

### Tablón sede Absis

- Tabla HTML con fecha, título, procedencia (unidad) y tipo de documento.
- Detalle vía popup `dlgVerDetalleAnuncio.aspx` con parámetro **`numint`** (no `numuint` como en otras sedes Absis).
- Filtro urbanismo: unidad `Oficina de Urbanismo-Planeamiento`, `Oficina Técnica`, edictos de planeamiento/urbanización.

### PGOU

- Página estática con enlaces a BOJA y buscador SITUA; sin listado estructurado de expedientes en curso (histórico documental).

## Licencias de obra

- **No hay dataset público** de concesiones de licencia con dirección/coordenadas.
- Tablón publica **calificación ambiental** de actividades (Oficina Técnica) — no licencias de obra concesionadas.
- Web municipal documenta trámites: licencia de obras, declaración responsable, ocupación vía pública (formularios PDF en cita previa).
- Estrategia adapter: filas informativas de trámites + edictos tablón con patrón licencia/ambiental.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** No existe visor urbanístico municipal ni ArcGIS/WFS del ayuntamiento. La Junta de Andalucía ofrece SITUA/VITUA a nivel regional (consulta por municipio/instrumento, sin enlace directo expediente↔polígono desde el tablón municipal).
- **Estrategia:** El orquestador aplicará centroide municipal + jitter. No se implementa `_fetch_geometry` (sin API enlazable por expediente).
- **Limitaciones:** Edictos y avisos en PDF/HTML sin georreferencia; detalle tablón requiere sesión ASP; SITUA no expone query determinista por código de expediente del tablón.

## Limitaciones generales

- Tablón mezcla RRHH, plenos y urbanismo; requiere filtrado por regex/unidad.
- RSS WordPress limitado a 10 ítems; el adapter pagina archivos de categoría.
- Detalle tablón (`numint`) devuelve 404 sin `sesionId` — se usa URL canónica con `numint` como clave estable.
- SSL sede válido; no requiere `insecure_ssl`.
