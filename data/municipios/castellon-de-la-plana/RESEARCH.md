# Castellón de la Plana — investigación portal ayuntamiento

**Municipio:** Castellón de la Plana (Castelló/Castellón, Comunitat Valenciana)  
**Slug:** `castellon-de-la-plana`  
**INE:** 12040  
**Boletín:** DOGV (`dogv`, 3 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.castello.es | **Bloqueada** — TLS connection reset en CI |
| Geoportal PG (histórico) | https://www.castello.es/es/geoportal-urbanistico | Misma IP; enlace al visor ESRI |
| Dominio PG (secuestrado) | https://plageneralcastello.es | **No operativo** — dominio aparcado (casino) |
| Sede electrónica | https://castello.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://castello.sedelectronica.es/board | **Operativa** — tabla HTML Wicket (~8 filas) |
| Portal transparencia sede | https://castello.sedelectronica.es/transparency/ | **Operativa** — sección 6 URBANISME (7 docs, AJAX) |
| Transparencia WP | https://transparencia.castello.es | **Operativa** — sin contenido urbanístico indexable |
| Catálogo trámites | https://castello.sedelectronica.es/dossier | Lenta; sin listado histórico scrapeable |
| Consulta expedientes | https://castello.sedelectronica.es/expedientes | Requiere autenticación |
| Registro planeamiento GVA | https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/3%20CASTELLÓN/12040%20CASTELLÓ%20DE%20LA%20PLANA/ | **Operativa** — índice Apache PG + PD |
| ICV WFS zonificación | https://terramapas.icv.gva.es/0702_Planeamiento | **Operativa** — GML, 70 polígonos municipio |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), bilingüe valenciano/castellano.
- **Listado:** tabla HTML con columnas estándar espublico (`class_name`, `class_folderCode`, …).
- **Documentos:** enlace `preview-document/{uuid}`.

### Ejemplos urbanísticos (ago 2026)

| Expediente | Descripción |
|------------|-------------|
| 1189/2024 | Anunci informació pública expropiació forçosa projecte construcció glorieta Pk 3+400 CV-560 |
| 2925/2026 | Anunci ampliació horari activitats recreatives (licencia actividad) |

## Registro planeamiento Generalitat (GVA)

Índice público en `mediambient.gva.es` con instrumentos vigentes:

**Plan General (6 carpetas):**

- 12040-1000 2021-0190 PLAN GENERAL
- 12040-1002/1003 PGMOD ejecución sentencia
- 12040-1100 PLAN ORDENACIÓN PORMENORIZADA
- 12040-1101 POPMOD Estaciones de servicio
- 12040-1102 POPMOD 2-2026 DIC

**Planificación diferida (7 carpetas):**

- 12040-0040 PE río seco 2019-0068
- 12040-0050 2021-0185 PEP CONVENTO DEL CARMEN
- 12040-2000 ED C_Sierra Alcaraz
- 12040-2010 ED manzana TRA-1, Av. Enrique Gimeno
- 12040-2020 PP s. urbanizable SR-Censal
- 12040-2030 PRI-M-57
- 12040-2040 ED UET-DOLZ

## Licencias de obra

- No hay dataset público de concesiones históricas.
- El tablón publica edictos puntuales (actividad recreativa, etc.).
- Trámites informativos en sede `/dossier` (timeout frecuente en CI).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV GVA WFS `Planeamiento.Zonificacion` (`terramapas.icv.gva.es/0702_Planeamiento`), filtro `cod_ine_mun=12040`, `srsName=EPSG:4326`, salida GML 3.2.
  - 70 polígonos de zonificación (9 tipologías únicas: ZND-IN, ZRC-AG, ZRP-*, ZUR-*, etc.) del Plan General expediente 20210190.
  - Geoportal municipal ESRI (Nexus Geographics) en `www.castello.es` / `plageneralcastello.es` — no accesible desde CI.
- **Estrategia:** el adapter descarga WFS por paginación (`startIndex`), convierte `posList` GML a GeoJSON WGS84 y enriquece proyectos del tablón/GVA por código expediente o palabras clave («plan general», tokens del título).
- **Limitaciones:**
  - WFS no admite `CQL_FILTER` ni `application/json` (solo GML/GPKG).
  - Zonificación ≠ delimitación de expediente individual; enlace indirecto por expediente PG.
  - Visor municipal y web corporativa inaccesibles en CI.
  - Transparencia sede sección urbanismo requiere Wicket AJAX (7 docs).

## Limitaciones generales

- `www.castello.es` no scrapeable (reset TLS).
- `plageneralcastello.es` dominio secuestrado.
- Tablón con pocos anuncios urbanísticos activos.
- Transparencia sede urbanismo vía AJAX; no determinista sin sesión Wicket.
- Consulta de expedientes requiere login.

## Adapter implementado

- `municipio.adapters.castellon_de_la_plana:CastellonDeLaPlanaAyuntamientoAdapter`
- Fuentes: tablón sede + índices GVA PG/PD + zonificación ICV WFS.
- IDs: `castellon-de-la-plana-lic-*` / `castellon-de-la-plana-proy-*` (sha256[:14]).
