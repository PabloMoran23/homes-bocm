# Santa María la Real de Nieva — investigación portal ayuntamiento

## Resumen

Municipio de la provincia de Segovia (Castilla y León). Web oficial en **WordPress** (`santamariadenieva.es`, redirige desde `www.santamarialarealdenieva.es`). La **sede electrónica** es **espublico gestiona** (`santamariadenieva.sedelectronica.es`).

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal WordPress | https://santamariadenieva.es |
| Normas subsidiarias / planeamiento local | https://santamariadenieva.es/normas-subsidiarias/ |
| Sede electrónica | https://santamariadenieva.sedelectronica.es |
| Tablón sede | https://santamariadenieva.sedelectronica.es/board |
| Trámites (catálogo) | https://santamariadenieva.sedelectronica.es/dossier |
| Archivo PLAI (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=185 |
| Archivo PLAI (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=40&municipio=185 |

## Expedientes / planeamiento

- **Web municipal:** PDFs en `/normas-subsidiarias/` (Normas Subsidiarias, TEI municipio). Sin sección «urbanismo» dedicada ni visor propio.
- **PLAI JCYL:** tabla HTML paginada (`searchVPubDocMuniPlau.do`, municipio **185**). Documentos de planeamiento aprobado e información pública.
- **Tablón sede:** tabla HTML con enlaces `preview-document/…` (Wicket). Octubre 2026: edictos electorales, enajenación patrimonio, bandos; pocos anuncios urbanísticos directos.
- **Sin API JSON** de expedientes en el portal municipal.

## Licencias de obra

- Trámites en sede espublico (`/dossier`, categorías de urbanismo/obras). Inicio con certificado electrónico.
- No hay listado público de licencias concedidas con coordenadas.
- El adapter incluye trámites informativos del catálogo y entradas del tablón cuando el título coincide con licencias/obras.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** IDECyL GeoServer WFS `urbanismo:plau_cyl_*` filtrado por `n_mun = 'Santa María la Real de Nieva'`:
  - `urbanismo:plau_cyl_instrumentos_ambito`
  - `urbanismo:plau_cyl_planes_parciales`
  - `urbanismo:plau_cyl_sectores`
- **Estrategia:** descarga WFS GeoJSON (`EPSG:4326`) + enriquecimiento por coincidencia de título/sector en filas PLAI, PDFs web y tablón.
- **Limitaciones:** sin visor ArcGIS municipal; licencias sin polígono; tablón mayoritariamente no urbanístico.

## Limitaciones generales

- Catálogo `/dossier` puede responder lento; timeouts ampliados en sede.
- Scrape determinista HTML + WFS + PLAI (sin LLM).
- `insecure_ssl: true` en manifest por compatibilidad con certificados de sede en algunos entornos CI.
