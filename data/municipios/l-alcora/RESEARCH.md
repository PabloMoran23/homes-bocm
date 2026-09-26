# L'Alcora — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `l-alcora` |
| INE | 12011 |
| Provincia | Castellón / Comunitat Valenciana |
| Boletín | DOGV (`dogv`, 2 entradas) |

## URLs base y páginas semilla

| Fuente | URL | Notas |
|--------|-----|-------|
| Web municipal | https://lalcora.es | WordPress (Yoast SEO, REST bloqueada con DRA) |
| Sede electrónica | https://lalcora.sedelectronica.es | espublico gestiona (Wicket/YUI) |
| Tablón de anuncios | https://lalcora.sedelectronica.es/board | Paginación `?page=N` (~10 filas/página) |
| Urbanismo | https://lalcora.es/arees-i-serveis-municipals/urbanisme/ | Sección municipal + enlaces a noticias |
| Portal transparencia | https://lalcora.sedelectronica.es/transparency | Carpeta «7. URBANISME…» (216 docs) |
| Catálogo trámites | https://lalcora.sedelectronica.es/dossier | Licencias vía sede (timeout ocasional) |
| Visor GVA | https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz | Capa ICV planeamiento |

## Cómo se listan expedientes / proyectos

1. **ICV WFS InventarioSuSuz:** 9 ámbitos SUZ/SUA aprobados para INE 12011 (sectores agrícola, barranc, monte, playa, etc.) con polígonos en GML3.
2. **Portal transparencia (espublico):** carpeta «7. URBANISME, OBRES PÚBLIQUES I MEDI AMBIENT» con 216 documentos; listado vía **Wicket AJAX** (no HTML estático).
3. **Tablón `/board`:** tabla HTML `class_name`, `class_folderCode`, `preview-document/{uuid}`; en la investigación había anuncio de información pública (concesión demanial vía pecuaria, exp. 7329/2022).
4. **Noticias WordPress:** sitemaps `post-sitemap.xml` + `post-sitemap2.xml`; artículos sobre modificaciones PGOU, pàrquing, etc. (REST API devuelve 401).

## Cómo se publican licencias

- No hay listado histórico público de licencias concedidas.
- Trámites de licencia vía sede (`/dossier`); catálogo no siempre responde en CI.
- Tablón publica edictos puntuales; sin licencias de obra activas en el momento de la investigación.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `InventarioSuSuz` en `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Parámetros: `outputFormat=GML3`, `srsName=EPSG:4326`, paginación `STARTINDEX`/`count=200`
  - Filtro en cliente: `cod_ine_mun=12011` (CQL_FILTER no fiable en este servicio)
  - Campos: `pp`, `ue`, `clasificacion`, `uso`, `f_aprob`, `f_public`
- **Estrategia:** descargar WFS paginado, convertir `posList` GML → GeoJSON Polygon WGS84; enriquecer filas tablón/noticias por coincidencia de sector/título.
- **Limitaciones:**
  - WFS no admite GeoJSON directo; solo GML3.
  - Página urbanismo integra visualización **Tableau Public** (sin API enlazable a expedientes).
  - Portal transparencia con 216 docs requiere sesión AJAX Wicket.
  - Licencias del tablón son PDFs sin georreferencia.

## Limitaciones generales

- WordPress REST API bloqueada (`DRA: Only authenticated users can access the REST API`).
- SSL sede: `insecure_ssl: true` recomendado en algunos entornos.
- Tablón mayoritariamente no urbanístico (festes, cobranzas, empleo público).

## Adapter

- `municipio.adapters.l_alcora:LAlcoraAyuntamientoAdapter`
- Fuentes: ICV WFS + tablón sede paginado + transparencia (metadatos) + noticias WP (sitemap) + páginas informativas licencias.
