# El Campillo — investigación portal ayuntamiento

**Municipio:** El Campillo (Valladolid, Castilla y León)  
**INE:** 47031 (código IDECyL/PLAI; cola regional `bocyl`)  
**Fecha:** 2026-09-14  
**BOCYL regional (referencia):** 1 aviso

## Resumen

El Campillo publica en el portal corporativo de la **Diputación de Valladolid**
(`elcampillo.ayuntamientosdevalladolid.es`, Liferay) y en sede electrónica **espublico gestiona**
(`campillo.sedelectronica.es`). El planeamiento aprobado está en **PLAI JCYL** (municipio **031**, provincia 47)
y el ámbito municipal en **IDECyL WFS** (NUM 2004). No hay sectores ni planes parciales cartografiados.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web municipal | `https://elcampillo.ayuntamientosdevalladolid.es` | Liferay (Dip. Valladolid) | Urbanismo, normativa, tablón de edictos |
| Tablón edictos | `.../tablon-de-edictos` | HTML Liferay | Modificación puntual NUM (2021), IP uso excepcional suelo rústico |
| Normativa urbanística | `.../normativa-urbanistica` | HTML | Enlaces a documentación |
| Sede electrónica | `https://campillo.sedelectronica.es` | espublico gestiona | Tablón `/board`, trámites `/dossier`, transparencia |
| PLAI JCYL | `servicios.jcyl.es/PlanPublica` (mun. **031**, prov. 47) | HTML tabla | NUM aprobada 2004 |
| IDECyL WFS | `idecyl.jcyl.es/geoserver/urbanismo/ows` | GeoJSON WFS | 1 instrumento NUM (ámbito municipal) |
| Web alternativa | `http://elcampillo.gob.es` | — | Redirige / inactiva en CI |

## Tablón de edictos (portal Dip. Valladolid)

Entradas urbanísticas documentadas (sin URL individual estable en muestra):

- **Aprobación inicial modificación puntual nº 1 NORMAS URBANÍSTICAS** (10 feb 2021)
- **Información pública:** autorización uso excepcional suelo rústico con protección natural hábitat +
  licencia urbanística — parcela 5004 polígono 6 (instalaciones alojamiento caballos)

## Sede electrónica (`campillo.sedelectronica.es`)

- Requiere **sesión caliente** (`/info.0` antes de `/dossier`); `/info` sin sufijo provoca bucle 302.
- `/board`: tablón actual con anuncios administrativos (electoral, subvenciones); sin urbanismo reciente.
- `/dossier`: catálogo de trámites (`/catalog/t/{uuid}`) — licencias y urbanismo como trámites informativos.
- `insecure_ssl: true` recomendado en CI.

## PLAI JCYL

Código municipio PLAI: **031** (provincia 47). Documento principal:

- **NORMAS URBANÍSTICAS MUNICIPALES** (NUM, aprobación 27/05/2004, BOCYL 26/08/2004)
- Índice: `openDocuIndice.do?cDocId=282440`

Sin documentos en información pública activa (`searchVPubDocMuniPlai` vacío).

## Licencias

No hay visor georreferenciado de concesiones de obra.

- Tablón web documenta IP de licencia urbanística (uso excepcional suelo rústico)
- Catálogo sede aporta trámites informativos de licencia/obra
- Sin listado tabular de concesiones con coordenadas

## Geometría / visor

- **geometry_status:** partial
- **Fuentes:**
  - WFS IDECyL `urbanismo:plau_cyl_instrumentos_ambito` — 1 polígono NUM municipal
  - Filtro: `n_mun = 'El Campillo'`, `outputFormat=application/json`, `srsName=EPSG:4326`
  - Sin capas `plau_cyl_sectores` ni `plau_cyl_planes_parciales` para este municipio
  - Visor SIUCyL: `https://idecyl.jcyl.es/siur/` (sin enlace directo a expediente)
- **Estrategia:** ingestar instrumento NUM desde WFS con `geom_geojson`; enriquecer filas PLAI/tablón
  por coincidencia de «normas urbanísticas» / NUM en título
- **Limitaciones:**
  - No hay geometría por expediente individual de licencia o IP parcelaria
  - Portal Dip. Valladolid puede timeout SSL en CI (semillas + PLAI/WFS como respaldo)
  - PLAI no expone coordenadas; solo PDF/BOCYL

## Limitaciones generales

- Portal Liferay Dip. Valladolid inestable en CI (handshake timeout)
- Sede `/info` sin sufijo → bucle redirect; usar `/info.0`
- Municipio pequeño: pocos expedientes públicos; dependencia de PLAI + WFS para proyectos
