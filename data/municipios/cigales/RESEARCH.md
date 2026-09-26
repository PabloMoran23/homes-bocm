# Cigales — investigación portal ayuntamiento

**Municipio:** Cigales (Valladolid, Castilla y León)  
**INE:** 47142 | **PLAU:** provincia 47, municipio 050  
**Fecha:** 2026-09-12  
**BOCYL (referencia):** 1 aviso

## Resumen

Cigales combina web corporativa **WordPress** (`cigales.es`) con sede electrónica **espublico gestiona**
(`cigales.sedelectronica.es`). El planeamiento urbanístico aprobado está centralizado en **PlanPublica / SiuCyL**
(JCYL). La cartografía sectorial y el ámbito del PGOU están en **IDECyL WFS**. No hay visor municipal propio
ni listado georreferenciado de licencias de obra concedidas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web municipal | https://cigales.es | WordPress (PHP 8.4) |
| Normativas urbanísticas | https://cigales.es/normativas-municipales/ | Ordenanzas + enlace Dropbox PGOU en tramitación |
| Sede electrónica | https://cigales.sedelectronica.es/info | espublico gestiona |
| Tablón de anuncios | https://cigales.sedelectronica.es/board/ | Tabla HTML Wicket, PDFs `preview-document/{uuid}` |
| Catálogo trámites | https://cigales.sedelectronica.es/dossier/.0 | Requiere cookie de sesión (~30 s primera carga) |
| PLAU JCYL (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=47&municipio=050 | 10 documentos (PGOU 2024, estudios detalle, convenio UE 37…) |
| PLAI JCYL (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=47&municipio=050 | Sin documentos activos (sep 2026) |
| SiUR visor regional | https://idecyl.jcyl.es/siur/index.html?id=47142 | Mapa interactivo CyL |

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente (en tramitación / reciente)

- **PGOU** aprobación definitiva **07/06/2024** (`cDocId=299924`) — instrumento principal actual.
- En la web municipal hay ZIP Dropbox con documentación PGOU «no vinculante, en tramitación».

### Listado PlanPublica (PLAU)

Página HTML con tabla ordenable. Campos: Libro (PU/GU/EU/CU/OT), subtipo, fechas, título, enlace PDF (`openDocumento.do?cDocId=`).

**Documentos identificados (sep 2026):**

| cDocId | Tipo | Fecha | Título |
|--------|------|-------|--------|
| 299924 | PGOU | 07/06/2024 | PLAN GENERAL DE ORDENACIÓN URBANA |
| — | CUG | 11/2022 | Convenio urbanístico UE nº 37 |
| 295555 | PPI | 05/03/2009 | Plan parcial industrial «Canal de Castilla» |
| 293592 | PE | 21/03/2012 | Plan especial infraestructuras Mucientes y Cigales |
| 284143/284520 | ED | 2008 | Estudios de detalle Av. Valladolid |
| 290411 | PRAT | 2006 | Plan regional ámbito territorial Canal de Castilla |
| … | histórico | — | PP La Garrapachina (1975), DOAS Valladolid entorno… |

Códigos PlanPublica: **provincia=47**, **municipio=050** (INE 47142).

## 3. Building licenses — tablón, sede, etc.

### Tablón de anuncios (`/board/`)

Tabla espublico: `Documento | Expediente | Procedimiento | Categoría | Descripción | Fecha`.

En la ventana visible (ago–sep 2026) predominan edictos fiscales (IAE, padrón vadós/agua), empleo público y
convocatorias electorales. **Sin licencias de obra** georreferenciadas.

### Catálogo de trámites (`/dossier/.0`)

Trámites informativos relevantes (no histórico de concesiones):

| Trámite | URL |
|---------|-----|
| Declaración Responsable o Comunicación Urbanística (Obra Menor) | `/catalog/t/3b44b504-5fae-4557-8b9f-f770442e0bd4` |
| Solicitud de Licencia o Autorización Urbanística | `/catalog/t/15fabacb-83b1-47d1-b435-508245672051` |
| Solicitud de Certificado o Informe Urbanístico | `/catalog/t/e247f7c3-b1ff-42ef-8b7d-5195c14e9bbf` |
| Solicitud de Actuación Urbanística | `/catalog/t/f91e4a50-d23d-45c1-a19b-b148da37c59f` |
| Solicitud de Licencia de Ocupación | `/catalog/t/b834b3fa-3690-4626-9c92-d82669d6f26f` |

**No existe** dataset ni visor de licencias concedidas con coordenadas.

## Geometría / visor

- **geometry_status:** partial
- **Fuentes:**
  - WFS IDECyL `urbanismo:plau_cyl_instrumentos_ambito` — 1 polígono PGOU (MultiPolygon)
  - WFS `urbanismo:plau_cyl_sectores` — 22 sectores (SUR-*, SU-NC *, Canal de Castilla, Guadalajara…)
  - Filtro: `n_mun ILIKE 'Cigales%'`, `outputFormat=application/json`, `srsName=EPSG:4326`
  - SiUR: `https://idecyl.jcyl.es/siur/index.html?id=47142`
- **Estrategia:** ingestar capas WFS como proyectos con `geom_geojson`; enriquecer filas PLAU/tablón por
  coincidencia de nombre de sector en título (Canal de Castilla, Guadalajara, UE 37…). Instrumento NUM/PGOU
  aporta polígono municipal completo.
- **Limitaciones:**
  - No hay geometría por expediente individual de licencia
  - PLAU/PLAI no exponen coordenadas; solo PDF/BOCYL
  - Tablón sin anuncios urbanísticos recientes en muestra
  - Dropbox PGOU es ZIP externo sin geometría embebida
  - Dossier sede requiere `insecure_ssl` + CookieJar (certificado caducado en cadena intermedia)

## Limitaciones generales

- PLAI vacío; fuente principal de planeamiento = PLAU JCYL
- WordPress REST API disponible pero pocas noticias urbanísticas indexables
- Sync Supabase requiere `SUPABASE_DB_URL` en entorno de ejecución
