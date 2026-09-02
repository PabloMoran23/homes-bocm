# San Cristóbal de Segovia — investigación portal ayuntamiento

## Resumen

Municipio de la provincia de Segovia (Castilla y León), INE 40172. El ayuntamiento publica su web en la plataforma **Liferay de la Diputación de Segovia** (`dipsegovia.es`); el dominio `www.sancristobaldesegovia.es` redirige al portal DipSegovia. La **sede electrónica** es **espublico gestiona** (`sancristobaldesegovia.sedelectronica.es`).

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal Liferay (DipSegovia) | https://www.dipsegovia.es/web/ayuntamiento-de-san-cristobal-de-segovia |
| Dominio municipal (alias) | https://www.sancristobaldesegovia.es |
| Urbanismo | https://www.dipsegovia.es/web/ayuntamiento-de-san-cristobal-de-segovia/urbanismo |
| Normativa urbanística | https://www.dipsegovia.es/web/ayuntamiento-de-san-cristobal-de-segovia/normativa-urban%C3%ADstica |
| Expedientes info pública | https://www.dipsegovia.es/web/ayuntamiento-de-san-cristobal-de-segovia/expedientes-en-tr%C3%A1mite-de-informaci%C3%B3n-p%C3%BAblica-y-documentaci%C3%B3n-previa |
| Sede electrónica | https://sancristobaldesegovia.sedelectronica.es |
| Tablón sede | https://sancristobaldesegovia.sedelectronica.es/board |
| Trámites (catálogo) | https://sancristobaldesegovia.sedelectronica.es/dossier |
| Archivo PLAI (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=170 |
| Archivo PLAI (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=40&municipio=170 |

## Expedientes / planeamiento

- **Urbanismo en web DipSegovia:** página con documentos PDF del planeamiento (NSPG, planos `sg317pl1`, `se317pl1`, memorias, guías). Incluye imagen de plano general y acordeón de documentos descargables.
- **PLAI JCYL:** tabla HTML paginada (`searchVPubDocMuniPlau.do`, municipio 170, provincia 40). Documentos históricos: Normas Subsidiarias de Planeamiento Municipal (1993), modificaciones puntuales, correcciones de errores materiales, etc.
- **Tablón sede:** tabla HTML con filas `preview-document/…` (Wicket). A agosto 2026: extractos de acuerdos de JGL, publicaciones de ordenanzas (no licencias de obra individuales).
- **Sin visor municipal propio** ni listado JSON de expedientes urbanísticos en curso.

## Licencias de obra

- Trámites en sede espublico (`/dossier`, catálogo `/catalog/t/…`); requieren certificado para iniciar.
- No hay listado público de licencias concedidas con coordenadas.
- El adapter incluye páginas informativas de trámites y entradas del tablón cuando aplican.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** IDECyL GeoServer WFS `urbanismo:plau_cyl_*` filtrado por `n_mun = 'San Cristóbal de Segovia'`:
  - `urbanismo:plau_cyl_instrumentos_ambito`
  - `urbanismo:plau_cyl_planes_parciales`
  - `urbanismo:plau_cyl_sectores` (12 features: Cotosaltos A/B UR1A/UR1B, El Cerezo A/B UR2A/UR2B, Eresma UR3, Los Caminos U1, UD1–UD2 U2–U3, Cerca del Abuelo U5, Cerca Barreros U6)
- **Estrategia:** descarga WFS GeoJSON (`EPSG:4326`) + enriquecimiento por coincidencia de título/sector en filas PLAI y tablón.
- **Limitaciones:** sin visor ArcGIS municipal; licencias sin polígono; expedientes del tablón no siempre enlazan a sector WFS.

## Limitaciones generales

- Sede `/dossier` puede responder lento; el adapter tolera timeout con `insecure_ssl`.
- Sin API JSON de expedientes; scrape determinista HTML + WFS + PLAI.
- Patrón replicable en otros municipios segovianos de DipSegovia (ver `bernuy_de_porreros`, `ituero_y_lama`).
