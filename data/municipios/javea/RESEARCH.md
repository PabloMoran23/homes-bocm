# Jávea (Xàbia) — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `javea` |
| INE | 03094 |
| Provincia | Alicante / Comunitat Valenciana |
| Boletín | DOGV (`dogv`, 5 entradas BOCM) |

## URLs base y páginas semilla

| Fuente | URL | Notas |
|--------|-----|-------|
| Web municipal | https://www.ajxabia.com | CMS VG Agencia Digital (MooTools/jQuery) |
| Sede electrónica | https://xabia.sedelectronica.es | espublico gestiona (Wicket/YUI) |
| Tablón de anuncios | https://xabia.sedelectronica.es/board | Edictos y anuncios públicos |
| Urbanismo (web) | https://www.ajxabia.com/ver/7151/urbanismo.html | Redirige a portal transparencia sede |
| Portal transparencia urbanismo | https://xabia.sedelectronica.es/transparency/fcfa421c-24d4-4865-8f58-3ea515cd827e/ | Sección 7 — Urbanismo, Obras Públicas y Medio Ambiente |
| Catálogo trámites | https://xabia.sedelectronica.es/dossier | Licencias vía sede (sin listado histórico) |
| CartoXàbia | Mencionado en noticia 2018 | Visor GIS municipal; sin URL/API pública estable en web |

## Cómo se listan expedientes / proyectos

1. **Portal transparencia (espublico):** carpeta «7. Urbanismo…» con subcarpetas:
   - 7.1 Planeamiento Urbanístico (2741 docs)
   - 7.3 Normativa Urbanística y Planes Sectoriales (30)
   - 7.4 Obras Públicas e Infraestructuras (24)
   - Los documentos se cargan vía **Wicket AJAX** (`wicketAjaxGet`); no hay listado HTML estático ni API REST pública.
2. **Tablón `/board`:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `preview-document/{uuid}`.
3. **ICV WFS InventarioSuSuz:** sectores SU/SUZ aprobados con polígonos (43 features para INE 03094).

## Cómo se publican licencias

- No hay listado público histórico de licencias concedidas en la web municipal.
- El tablón sede publica edictos puntuales (notificaciones, cobranzas); en el momento de la investigación no había licencias de obra activas.
- Trámites de licencia vía sede (`/dossier`) y consulta de expedientes (`/expedientes`, requiere identificación).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `InventarioSuSuz` en `https://terramapas.icv.gva.es/0702_Planeamiento/ows`
  - Parámetros: `outputFormat=GML3`, `srsName=EPSG:4326`, paginación `STARTINDEX`/`count=200`
  - Filtro en cliente: `cod_ine_mun=03094`
  - Campos: `pp`, `ue`, `clasificacion`, `uso`, `f_aprob`, `f_public`
- **Estrategia:** descargar WFS paginado, convertir `posList` GML → GeoJSON Polygon WGS84; enriquecer filas tablón/transparencia por coincidencia de título.
- **Limitaciones:**
  - WFS no admite `CQL_FILTER` ni `application/json`; solo GML3.
  - CartoXàbia (visor municipal) no expone API enlazable a expedientes.
  - Portal transparencia con 2741 docs requiere sesión AJAX; no scrapeable de forma determinista sin reverse del protocolo Wicket.
  - Licencias del tablón son PDFs sin georreferencia.

## Limitaciones generales

- SSL sede: certificado con problemas en algunos entornos → `insecure_ssl: true`.
- Tablón actual mayoritariamente no urbanístico (oposiciones, cobranzas tributarias).
- Web municipal sin PDFs de planeamiento indexables por búsqueda interna.

## Adapter

- `municipio.adapters.javea:JaveaAyuntamientoAdapter`
- Fuentes: ICV WFS + tablón sede + carpetas transparencia (metadatos) + páginas informativas licencias.
