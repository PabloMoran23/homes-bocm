# Palmera — investigación portal ayuntamiento

**Municipio:** Palmera (Valencia, Comunitat Valenciana)  
**Slug:** `palmera`  
**INE:** 46198  
**Boletín:** DOGV (`dogv`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.palmera.es | Operativa (TLS intermitente en cloud; `insecure_ssl` + reintentos) |
| Urbanisme (ES) | https://www.palmera.es/es/pagina/urbanisme | Operativa |
| Urbanisme (VA) | https://www.palmera.es/va/pagina/urbanisme | Operativa |
| Instàncies i sol·licituds | https://www.palmera.es/es/pagina/instancies-sollicituds | Formularios obra/licencias |
| Anuncios web | https://www.palmera.es/es/listado-titulares/anuncio | Listado Drupal |
| Sede electrónica | https://palmera.sedelectronica.es | Operativa — espublico gestiona |
| Tablón de anuncios | https://palmera.sedelectronica.es/board | Operativa — edictos (BOP, anuncios previos web) |
| Transparencia sede | https://palmera.sedelectronica.es/transparency | Sección 6 Urbanisme (43 docs, Wicket/AJAX) |
| Catálogo trámites | https://palmera.sedelectronica.es/dossier | Trámites licencias (sin histórico público) |
| Consulta expedientes | https://palmera.sedelectronica.es/expedientes | Requiere autenticación |

## Cómo se listan expedientes

- **Planeamiento vigente:** inventario ICV GVA `InventarioSuSuz` (WFS) con **7** ámbitos (UE/SUZ) para INE 46198.
- **Tablón sede:** tabla HTML Wicket en `/board` (documento, expediente, procedimiento, fecha).
- **Web Drupal:** páginas `/es/pagina/urbanisme` y PDFs en `/sites/www.palmera.es/files/` cuando accesibles.
- **Transparencia sede:** carpeta «6. URBANISME…» con documentos; navegación vía AJAX (no scrapeada en detalle).

## Licencias de obra

- Formularios en instàncies (comunicación previa, licencias).
- Tablón publica anuncios previos («Anunci previ portal web») sin dataset estructurado de concesiones.
- Adapter incluye páginas informativas de trámites + filas del tablón cuando encajan patrones de licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Capa `ms:InventarioSuSuz`, filtro client-side `cod_ine_mun=46198` (7 polígonos: UE-1, UE-2, UE-5, UE-6, UE-PZ. ST. VICENT, etc.)
  - Visor GVA: `https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz`
- **Estrategia:** paginación WFS (200 features/página) hasta cubrir inventario; GML → GeoJSON EPSG:4326; proyectos ICV como filas `proyectos.jsonl`; match por sector/UE en títulos del tablón/web.
- **Limitaciones:**
  - `CQL_FILTER` del WFS no filtra por municipio en servidor; filtro en cliente.
  - Geometría solo para instrumentos de planeamiento ICV (no licencias de obra).
  - `www.palmera.es` puede hacer timeout TLS desde algunos entornos.
  - Sin visor ArcGIS municipal propio.

## Limitaciones generales

- Tablón paginado Wicket (primera página en scrape estático).
- Consulta expedientes requiere login.
- Web bilingüe valenciano/castellano (`/va/` y `/es/`).
- Provincia en `queue.yaml` aparece como `Palmera`; manifest usa `Valencia`.

## Adapter implementado

- `municipio.adapters.palmera:PalmeraAyuntamientoAdapter`
- Fuentes: ICV WFS + páginas Drupal (semillas) + tablón sede + trámites informativos.
