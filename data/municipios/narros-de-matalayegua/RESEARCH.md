# Narros de Matalayegua — investigación portal ayuntamiento

**Municipio:** Narros de Matalayegua (provincia Salamanca, Castilla y León)  
**Fecha:** 2026-09-26  
**BOCYL (referencia):** 1 aviso  
**INE:** 37212 | **DIR3:** L01372112

## Resumen

Narros de Matalayegua **no tiene web corporativa** (`www.narrosdematalayegua.es` no resuelve). La administración digital se concentra en la **sede electrónica espublico gestiona** (`narrosdematalayegua.sedelectronica.es`). El planeamiento urbanístico publicado está en **PlanPublica** (Junta de CYL, código municipio **211** en provincia 37). No hay listado público de licencias de obra concedidas con coordenadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Sede electrónica | https://narrosdematalayegua.sedelectronica.es/info | Redirige desde `/` |
| Tablón de anuncios | https://narrosdematalayegua.sedelectronica.es/board | Tabla Wicket + PDFs `preview-document` |
| Trámites | https://narrosdematalayegua.sedelectronica.es/dossier | Catálogo espublico (carga lenta) |
| Transparencia | https://narrosdematalayegua.sedelectronica.es/transparency | Sin sección urbanismo destacada |
| PlanPublica PLAU | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=211 | Archivo planeamiento aprobado |
| PlanPublica PLAI | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=211 | Información pública (sin filas activas sep 2026) |
| SiuCyL / SiUR | https://idecyl.jcyl.es/siur/index.html?id=37212 | Visor regional de instrumentos |

**Contacto:** C/ Real 105, 37609 Narros de Matalayegua · Tel. 923 390 009 · aytonarrosmatalayegua@yahoo.es

**Limitación SSL:** el certificado de la sede no encadena con CA del sistema (`unable to get local issuer certificate`). El adapter usa `insecure_ssl: true` solo para hosts `*.sedelectronica.es` de este municipio.

## 2. Urbanismo / expedientes

### PlanPublica (PLAU)

Tabla HTML con filas `Libro / Tipo / fechas / Título`. En sep 2026 hay al menos:

| Tipo | Subtipo | Fecha pub. | Título |
|------|---------|------------|--------|
| PU | DSU | 28/01/1999 | DSU Y ANEJOS |

Enlaces PDF vía `openDocumento.do?cDocId=…` o `doOpen('…')` en JavaScript embebido.

### Tablón de anuncios

Listado paginado con columnas documento, expediente, procedimiento, categoría, descripción, fecha. En la muestra consultada predominan avisos no urbanísticos (caza, cobranza). Sin licencias de obra explícitas.

### Licencias

No hay dataset ni tablón dedicado a concesiones georreferenciadas. Trámites de licencia existen en el catálogo de la sede (UUID por municipio); el adapter no hardcodea UUIDs y deja filas de licencia vacías salvo anuncios futuros en tablón.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_sectores`
  - Filtro: `CQL_FILTER=n_mun='Narros de Matalayegua'`
  - SiUR visor regional por INE `37212` (sin enlace directo expediente↔polígono en sede)
- **Estrategia:** descarga WFS por municipio; polígono del instrumento de ámbito (DSU/NUM) en proyectos PLAU; sectores solo si aparecen códigos en títulos.
- **Limitaciones:** sin visor municipal; licencias sin geometría; sede con SSL intermedio roto; municipio pequeño con un instrumento histórico en PLAU.

## 3. Implementación adapter

Patrón **Valverdón / Monfarracinos (CYL):** `urllib` + `insecure_ssl` en sede, parseo PLAU, enriquecimiento WFS (`geom_geojson`, `geometry_source=portal_wfs`).
