# Nava de la Asunción — investigación portal ayuntamiento

## Resumen

Municipio de la provincia de Segovia (Castilla y León). El ayuntamiento publica su web corporativa en **WordPress** (`navadelaasuncion.org`). La **sede electrónica** (`navadelasuncion.sedelectronica.es`, espublico gestiona) responde con página **"Sede Electrónica Indeterminada"** en todos los endpoints probados (`/board`, `/dossier`, `/transparency`, `/info.0`). El planeamiento urbanístico se consulta principalmente en el **archivo PLAI** de la Junta de CYL y en el **visor SIUR/IDECyL**.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (WordPress) | https://navadelaasuncion.org |
| Sede electrónica | https://navadelasuncion.sedelectronica.es |
| Enlace sede desde web | https://navadelaasuncion.org/ayuntamiento/oficina-virtual/sede-electronica/ |
| Archivo PLAU (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=138 |
| Archivo PLAI (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=40&municipio=138 |
| Visor SIUR (IDECyL) | https://idecyl.jcyl.es/siur/index.html?id=40138 |
| DipSegovia (ayuntamiento) | https://www.dipsegovia.es/web/ayuntamiento-de-nava-de-la-asuncion — **404** |

## Expedientes / planeamiento

- **Web municipal:** sin sección de urbanismo ni tablón de anuncios. Noticias vía WordPress REST API (`/wp-json/wp/v2/posts`); pocas entradas urbanísticas (p. ej. instalación solar fotovoltaica).
- **PLAI/PLAU JCYL:** tabla HTML con ~15 documentos aprobados (planes parciales «El Rancho», «A», sector E-1 Navaciruela, estudios de detalle, PAU sector B-1-1, etc.) y 1 expediente en información pública (modificación NUM sector U7, julio 2026).
- **Sede espublico:** no operativa (subdominio sin configurar). No hay tablón ni catálogo de trámites accesible.
- **Sin visor municipal propio**; el visor regional es SIUR (IDECyL).

## Licencias de obra

- No hay listado público de licencias concedidas.
- La sede electrónica no responde con catálogo de trámites.
- El adapter incluye la página informativa de sede desde la web municipal como referencia de trámite.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL GeoServer WFS `urbanismo:plau_cyl_*` filtrado por `c_mun='40138'`:
    - `urbanismo:plau_cyl_instrumentos_ambito` (1 feature)
    - `urbanismo:plau_cyl_planes_parciales` (1 feature)
    - `urbanismo:plau_cyl_sectores` (18 features: sectores B-1-1, El Rancho, etc.)
  - Visor SIUR: https://idecyl.jcyl.es/siur/index.html?id=40138 (Ionic SPA; geometría vía WFS)
- **Estrategia:** descarga WFS GeoJSON (`EPSG:4326`) + enriquecimiento por coincidencia de sector/código en filas PLAI.
- **Limitaciones:** sede inaccesible; licencias sin polígono; noticias WP sin georreferencia; estudios de detalle sin sector WFS enlazable.

## Limitaciones generales

- Sede electrónica espublico no configurada (respuesta "Indeterminada").
- Sin página DipSegovia Liferay para este municipio.
- Sin API JSON de expedientes locales; scrape determinista PLAI + WFS + WP REST.
- Boletín regional: BOCYL (3 entradas históricas en CSV).
