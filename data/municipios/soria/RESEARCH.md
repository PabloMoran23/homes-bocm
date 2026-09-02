# Soria — investigación portal ayuntamiento

**Municipio:** Soria (capital provincial, Castilla y León)  
**Fecha:** 2026-09-02  
**BOCYL (referencia):** 2 avisos  
**INE:** 42173

## Resumen

Soria capital publica urbanismo y licencias principalmente en la **sede electrónica espublico gestiona**
(`soria.sedelectronica.es`). El planeamiento histórico (PERI-PECH, NUM, planes parciales) está en
**PlanPublica / SiuCyL** (Junta de Castilla y León). La geometría de sectores e instrumentos está
disponible en el **WFS IDECyL**. La web corporativa `soria.es` responde con protección Cloudflare
desde entornos automatizados; no es necesaria para la ingesta.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web corporativa | https://soria.es | Cloudflare challenge (403 en curl) |
| Sede electrónica | https://soria.sedelectronica.es/info | espublico gestiona / Wicket |
| Tablón de anuncios | https://soria.sedelectronica.es/board/ | Tabla HTML con PDFs `preview-document/{uuid}` |
| Catálogo de trámites | https://soria.sedelectronica.es/dossier | Requiere cookie de sesión (~5 s tras `/board/`) |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=42&municipio=1 | Tabla HTML con `openDocuIndice.do?cDocId=` |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=42&municipio=1 | 1 documento activo (sep 2026) |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=42173 | Visor regional interactivo |

Códigos PlanPublica: **provincia=42** (Soria), **municipio=1** (Soria capital).

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente y histórico

- **NUM** (Normas Urbanísticas Municipales), aprobación definitiva **07/11/2001** (`cDocId` en PLAU).
- **PERI-PECH Soria** (Plan Especial de Reforma Interior del Casco Histórico): múltiples modificaciones
  puntuales (U-1, U-25, U-29, etc.) en PLAU.
- Planes parciales históricos (sectores P-3 «Eras de Santa Bárbara», Sector III, etc.).

### Listado PlanPublica (PLAU)

Página HTML con tabla ordenable. Campos: tipo instrumento (PU/GU/EU/SU), subtipo (NS, PERI, PP, NUM),
fechas, título, enlace `openDocuIndice.do?cDocId={id}`.

Ejemplos recientes en tablón (sep 2026):

- Expediente **37168/2026** — «Aprobación inicial del Proyecto de Normalización UN-10 PERI-PECH Soria»
  (parcelas catastrales 44380-1 y 4430-11, Calle Caballeros 29 / Calle Alberca 1).

### Tablón sede (`/board/`)

Columnas: Documento | Expediente | Procedimiento | Categoría | Descripción | Fecha.

- Categoría **Urbanismo** / procedimiento **Actuaciones Urbanísticas** con PDFs en
  `https://soria.sedelectronica.es/preview-document/{uuid}`.
- Sin paginador público evidente; ventana de ~10 filas visibles.

## 3. Building licenses

No hay dataset público de licencias concedidas con coordenadas. El catálogo de trámites incluye:

| Trámite | URL |
|---------|-----|
| Declaración responsable actuaciones sencillas | `/catalog/t/c52dcecf-5159-41d1-8fd8-1d2cf7b69a2a` |
| Solicitud de Licencia o Autorización Urbanística | `/catalog/t/15fabacb-83b1-47d1-b435-508245672051` |
| Solicitud de licencia de obra mayor | `/catalog/t/b3e341df-0750-405c-bbfd-911d503efd70` |
| Modificación o Renuncia de Licencia Urbanística | `/catalog/t/a3c783fb-bb19-4ea3-b40f-0072d69aebae` |
| Licencia de Ocupación | `/catalog/t/b834b3fa-3690-4626-9c92-d82669d6f26f` |
| Primera ocupación o utilización | `/catalog/t/56a24794-bb82-4b2f-9704-c6b5a07a3061` |
| Certificado o Informe Urbanístico | `/catalog/t/e247f7c3-b1ff-42ef-8b7d-5195c14e9bbf` |
| Licencia Ambiental | `/catalog/t/639337f0-58f8-4ee0-9acd-498b5e97d4ed` |

Son páginas informativas de solicitud, no histórico de concesiones.

## 4. CMS / tecnología

| Componente | Stack |
|------------|-------|
| Sede electrónica | **espublico gestiona** (`com.espublico.expedientes.*`) sobre **Apache Wicket** + nginx |
| Web corporativa | WordPress / Cloudflare (no scrapeable sin browser) |
| Planeamiento regional | **PlanPublica** — portal Java/JSP (Junta CyL) |
| GIS regional | **GeoServer** (IDECyL) + visor **SiUR** |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `plau_cyl_sectores` (72 polígonos), `plau_cyl_planes_parciales` (6), `plau_cyl_instrumentos_ambito` (1 NUM)
  - Filtro: `n_mun = 'Soria'`
  - SiUR: `https://idecyl.jcyl.es/siur/index.html?id=42173`
- **Estrategia:** ingestar geometría desde WFS por sector/instrumento; cruzar códigos UN/PERI/SE del
  título del tablón o PLAU con `n_num_sect` / `c_id_sect`; centroide municipal para licencias informativas.
- **Limitaciones:** tablón y trámites sin GIS enlazable; SiUR no expone API directa al scrapeador;
  web corporativa bloqueada por Cloudflare.

### WFS — ejemplo de consulta

```
GET https://idecyl.jcyl.es/geoserver/urbanismo/wfs
  ?service=WFS&version=2.0.0&request=GetFeature
  &typeNames=urbanismo:plau_cyl_sectores
  &outputFormat=application/json
  &srsName=EPSG:4326
  &CQL_FILTER=n_mun='Soria'
```

## Limitaciones

- Sin listado histórico público de licencias concedidas con coordenadas.
- Tablón: ventana corta, sin API ni paginación clara.
- PLAU: documentación histórica mayoritariamente pre-2010; instrumento vigente NUM + PERI.
- Web `soria.es`: Cloudflare impide scrape directo.

## Estrategia adapter

1. **WFS IDECyL** → proyectos con `geom_geojson` (sectores, planes parciales, ámbito NUM).
2. **PlanPublica PLAU/PLAI** → parsear tabla HTML (`openDocuIndice.do`, fechas, títulos).
3. **Tablón sede** (`/board/`) → filtrar urbanismo/licencias; PDFs `preview-document/{uuid}`.
4. **Catálogo dossier** → licencias informativas (`/catalog/t/{uuid}`).
5. **IDs:** `soria-{lic|proy}-{sha256[:14]}`.
