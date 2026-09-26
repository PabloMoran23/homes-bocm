# Nava del Rey — investigación portal ayuntamiento

**Municipio:** Nava del Rey (provincia Valladolid, Castilla y León)  
**Fecha:** 2026-09-26  
**BOCYL (referencia):** 1 aviso  
**INE:** 47102 | **CIF:** P4710200I

## Resumen

Nava del Rey combina **web institucional WordPress** (`ayto-navadelrey.com`) con **sede electrónica espublico gestiona** (`navadelrey.sedelectronica.es`). El planeamiento aprobado e información pública están en **PlanPublica** (Junta de CYL). La geometría de sectores e instrumentos está en **IDECyL WFS** (`urbanismo:plau_cyl_*`). No hay listado público de concesiones de licencias georreferenciadas; el tablón publica sobre todo plenos y tributos.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web institucional | https://ayto-navadelrey.com/ | WordPress + GeneratePress child theme; enlace a sede en cabecera |
| Sede electrónica | https://navadelrey.sedelectronica.es/ | espublico gestiona (Wicket) |
| Tablón de anuncios | https://navadelrey.sedelectronica.es/board/ | Tabla HTML con `preview-document/{uuid}` |
| Catálogo trámites | https://navadelrey.sedelectronica.es/dossier/.0 | Redirección en bucle desde algunos clientes; catálogo estándar espublico accesible por UUID |
| PlanPublica PLAU | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=47&municipio=102 | Archivo planeamiento aprobado |
| PlanPublica PLAI | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=47&municipio=102 | Información pública |
| SiuCyL / SiUR | https://idecyl.jcyl.es/siur/index.html?id=47102 | Visor regional |

**Contacto:** Plaza España 1, 47500 Nava del Rey · Tel. 983 850 111 · info@ayto-navadelrey.com

## 2. Urbanismo — expedientes / planeamiento

### PlanPublica (PLAU / PLAI)

- Listado HTML tabla `#listado`; enlaces `openDocumento.do?cDocId=…` y códigos `47102-PU-…` / `47102-GU-…`.
- Ejemplo histórico NUM: `47101-PU-20140422-290590` (`cDocId=290590`, aprobación definitiva 22/04/2014).
- PLAI puede incluir expedientes en trámite (p. ej. modificaciones de planeamiento).

### Sede — tablón

- Filas con columnas documento, expediente, procedimiento, categoría, descripción, fecha.
- En septiembre 2026 predominan convocatorias de pleno, tributos y padrones; pocos avisos de urbanismo en tablón.

### Trámites (catálogo espublico)

UUIDs de trámite urbanístico compartidos con otras sedes espublico (p. ej. licencia urbanística `15fabacb-83b1-47d1-b435-508245672051`). El adapter los usa como **páginas informativas** de licencias (sin concesiones publicadas).

## 3. Licencias de obra

- **No** hay dataset ni tablón sistemático de licencias concedidas con dirección.
- Estrategia: tablón (si aparece licencia) + páginas de catálogo de trámites de licencia/comunicación previa.

## Geometría / visor

- **geometry_status:** `available`
- **Fuentes:**
  - WFS IDECyL `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_instrumentos_ambito`
  - Filtro: `n_mun = 'Nava del Rey'` (15 sectores en WFS, sep 2026)
  - Visor: SiUR `id=47102` (consulta por municipio, sin enlace directo expediente-tabla)
- **Estrategia:** `GetFeature` GeoJSON `EPSG:4326`; enriquecer proyectos WFS y cruzar códigos de sector en títulos PLAU/tablón vía `_wfs_sector_geometry`.
- **Limitaciones:** Licencias sin polígono; tablón sin GIS; dossier puede dar 302 en bucle sin cookies de sesión.

## 4. Adapter implementado

- Módulo: `municipio/adapters/nava_del_rey.py` (`NavaDelReyAyuntamientoAdapter`)
- Patrón: Valverdón / Monfarracinos (espublico + PlanPublica + WFS)
- IDs: `nava-del-rey-{lic|proy}-{sha256[:14]}`
