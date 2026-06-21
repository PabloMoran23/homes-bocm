# Villanueva de la Cañada — investigación portal ayuntamiento

**Fecha:** 2026-06-20  
**Slug:** `villanueva-de-la-canada`  
**BOCM regional (referencia):** 43 filas

## Resumen

Villanueva de la Cañada publica planeamiento y trámites urbanísticos en **dos portales complementarios**, integrados en la plataforma **Región Digital Madrid Noroeste** (compartida con Las Rozas, Majadahonda, Torrelodones, etc.):

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://www.ayto-villacanada.es | WordPress Avada | Urbanismo, PGOU, planes parciales, expedientes IP, licencias (trámites) |
| Sede electrónica | https://portal.ayto-villacanada.es | STA / tablón virtual | Bandos, tablón electrónico (`ent_id=6`) |

## Fuentes de proyectos / expedientes

### 1. Expedientes urbanísticos (WordPress)

- **URL:** https://www.ayto-villacanada.es/urbanismo-y-vivienda/expedientes-urbanisticos/
- **Formato:** HTML Avada con paneles acordeón (*En Información Pública*, *En Tramitación*).
- **Contenido:** Anuncios de reparcelación, memorias, planos (PDF en `wp-content/uploads/`).
- **Ejemplo (jul 2025):** Reparcelación Sector 1 — `Anuncio-Reparcelación-SEctor-1.pdf`, `Memoria-Sin-Interesados.pdf`.

### 2. Plan General de Ordenación Urbana

- **URL:** https://www.ayto-villacanada.es/urbanismo-y-vivienda/plan-general-de-ordenacion-urbana/
- **Formato:** HTML con ~68 enlaces PDF (zonas: Ciudad Jardín, Deportivo, Ensanche, etc.) en `/sites/default/files/files/`.

### 3. Planes parciales (sectores 1, 2, 4)

- **Sector 1:** https://www.ayto-villacanada.es/urbanismo-y-vivienda/plan-parcial-sector-1/ (~54 PDFs: memorias, planos, normativa)
- **Sector 2:** https://www.ayto-villacanada.es/urbanismo-y-vivienda/plan-parcial-sector-2/ (~12 PDFs)
- **Sector 4:** https://www.ayto-villacanada.es/urbanismo-y-vivienda/plan-parcial-sector-4/ (~9 PDFs)

### 4. Planes especiales

- **URL:** https://www.ayto-villacanada.es/urbanismo-y-vivienda/planes-especiales/
- **Contenido:** Plan Especial Ampliación EDAR (PDF 2024).

### 5. Tablón virtual — Bandos urbanismo (`TV_BAN_URB`)

- **URL:** `https://portal.ayto-villacanada.es/portal/tablonVirtual.do?subseccion=TV_BAN_URB&opc_id=175&ent_id=6&idioma=1`
- **Formato:** HTML tabla `Lista2` (7 columnas: año, código, tipo, nombre, fecha creación, fecha publicación, estado).
- **Contenido:** Bandos y notificaciones urbanísticas. Detalle en `?expId=<id>`.
- **Limitación:** Subconjunto reciente (p. ej. 1 expediente en jun 2026); sin histórico completo.

### 6. Tablón virtual — Bandos generales (`TV_BAN`)

- **URL:** `https://portal.ayto-villacanada.es/portal/tablonVirtual.do?subseccion=TV_BAN&opc_id=175&ent_id=6&idioma=1`
- **Contenido:** Bandos varios; se filtran filas con palabras clave urbanísticas/licencias.

## Fuentes de licencias

**No hay listado público de licencias concedidas** con geolocalización (a diferencia de Madrid capital).

Fuentes disponibles:

1. **Licencias urbanísticas (informativo):** https://www.ayto-villacanada.es/urbanismo-y-vivienda/licencias-urbanisticas/  
   Páginas de trámites (instancias PDF, ordenanzas). No son concesiones publicadas.

2. **Tablón virtual `TV_BAN`:** tipos como `LICENCIA DE UTILIZACION DEL DOMINIO PUBLICO` — publicaciones administrativas, no licencias de obra con coordenadas.

3. **Sede electrónica — trámite genérico:** Solicitud a Oficina Técnica y Urbanismo (requiere certificado digital).

## Limitaciones

- Tablón virtual con pocas filas activas; sin API JSON ni paginación histórica.
- PDFs del tablón requieren código de verificación CSV para descarga directa.
- Sin datos abiertos georreferenciados de licencias (`lat`/`lon`/`distrito` siempre `null`).
- Web WordPress mezcla PDFs de planeamiento con documentos administrativos (certificados ENS); se filtran por regex.
- No replicar pipeline Madrid capital (`sector_geometry/madrid_*`).

## Estrategia de ingesta

Adapter híbrido estilo Torrejón (tablón STA) + Las Rozas (crawl PDF WordPress):

| Dataset | Fuente principal | Secundaria |
|---------|------------------|------------|
| `proyectos.jsonl` | Expedientes IP + planes parciales/PGOU (PDFs WP) | Tablón `TV_BAN` + `TV_BAN_URB` |
| `licencias.jsonl` | Tablón (tipos LICENCIA*) | Página trámites licencias (informativo) |

IDs estables: `villanueva-de-la-canada-{lic|proy}-{sha256[:14]}`.
