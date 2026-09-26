# Fuensaldaña — investigación portal ayuntamiento

**Municipio:** Fuensaldaña (provincia Valladolid, Castilla y León)  
**Fecha:** 2026-09-16  
**BOCYL (referencia):** 1 aviso  
**INE:** 47120

## Resumen

Fuensaldaña **no dispone de web corporativa propia** (`fuensaldana.es` no resuelve). Toda la presencia digital municipal pasa por la **sede electrónica espublico gestiona** (`fuensaldana.sedelectronica.es`). El planeamiento urbanístico está centralizado en **PlanPublica / IDECyL WFS** (Junta de Castilla y León). No hay visor urbanístico municipal ni listado público de concesiones de licencias georreferenciadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Sede electrónica (inicio) | https://fuensaldana.sedelectronica.es/info | Redirige desde `/info` |
| Tablón de anuncios | https://fuensaldana.sedelectronica.es/board/ | Responde de forma fiable |
| Catálogo de trámites | https://fuensaldana.sedelectronica.es/dossier | Requiere cookie de sesión; `/dossier/.0` provoca bucle de redirección |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=47&municipio=120 | Sin documentos indexados (sep 2026) |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=47&municipio=120 | Sin documentos activos |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=47120 | Mapa interactivo regional |

## 2. Urban planning — expedientes / planeamiento

### Fuentes de datos

1. **IDECyL WFS** — capas `plau_cyl_instrumentos_ambito` (1), `plau_cyl_planes_parciales` (4), `plau_cyl_sectores` (20) con filtro `n_mun='Fuensaldaña'`.
2. **Tablón de anuncios** (`/board/`) — HTML Wicket con tabla de anuncios; en sep 2026 sin entradas de urbanismo activas (solo administrativos).
3. **Catálogo de trámites** (`/dossier`) — páginas informativas de licencias y planeamiento (UUIDs estándar espublico).
4. **PlanPublica** — listado vacío; la geometría y metadatos provienen del WFS.

### Sectores identificados (WFS, sep 2026)

| Código | Nombre |
|--------|--------|
| SEC-01 | Camino del Sotillo |
| SEC-02 | Arroyo Valcavado |
| SEC-03 | Arroyo de las Monjas |
| SEC-04 | Camino de Ciguñuela |
| SEC-05 | Camino Monjo |
| SEC-06 | La Ermita-1 |
| SEC-07 | Camino de la Cuesta |
| SEC-08 | Cementerio |
| SEC-09 | Carretera Valladolid a Mucientes |
| SEC-13 | Palillos |
| SEC-14 | La Ermita-2 |
| SEC-15.1 | Bodegas La Horca-1 |
| SEC-15.2 | Bodegas La Horca-2 |
| SEC-16 | Valdecarros |
| SEC-17 | Torremormojón |
| SEC-18 | Industria El Molar |
| SEC-A | Camino de la Mona |
| 10 | La Atalaya |
| 11 | Viñales |
| 12 | Los Erizos |

### Licencias

No hay tablón público de concesiones de licencias de obra. El adapter recoge páginas informativas de trámites del catálogo (`/dossier`) y anuncios del tablón con categoría «Licencias de Ocupación».

## 3. Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** IDECyL WFS `https://idecyl.jcyl.es/geoserver/urbanismo/wfs` — capas `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_sectores`; filtro CQL `n_mun='Fuensaldaña'`; `outputFormat=application/json`, `srsName=EPSG:4326`.
- **Estrategia:** Descarga masiva por capa WFS al backfill; enriquecimiento por código de sector (`SEC-XX`) en filas del tablón/PLAU mediante query puntual a `plau_cyl_sectores`.
- **Limitaciones:** Sin visor municipal; licencias del tablón sin geometría enlazable; PLAU sin documentos HTML indexados (solo WFS). SiuCyL requiere navegador para consulta interactiva.

## 4. Limitaciones técnicas

- `/dossier/.0` provoca bucle de redirección HTTP 302; usar `/dossier` con cookie jar.
- Primera carga del dossier ~10–15 s.
- SSL de la sede requiere `insecure_ssl: true` en algunos entornos.
- IDs estables: `fuensaldana-{lic|proy}-{sha256[:14]}`.
