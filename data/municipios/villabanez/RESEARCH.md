# Villabáñez — investigación portal ayuntamiento

**Municipio:** Villabáñez (provincia Valladolid, Castilla y León)  
**Fecha:** 2026-09-04  
**BOCYL (referencia):** 2 avisos  
**INE:** 47195

## Resumen

Villabáñez publica trámites y tablón en la **sede electrónica espublico gestiona**
(`villabanez.sedelectronica.es`). El planeamiento urbanístico vigente (NUM + PERI «Dehesa de Peñalba»)
está en **PlanPublica / SiuCyL** (Junta de Castilla y León). La geometría de sectores e instrumentos
está disponible vía **WFS IDECyL**. No hay visor urbanístico municipal ni listado público de licencias
de obra concedidas con coordenadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web corporativa | https://villabanez.es/ | Redirige / timeout frecuente desde agente |
| Portal Diputación | https://villabanez.ayuntamientosdevalladolid.es/ | Noticias y enlaces; sede en subdominio propio |
| Sede electrónica | https://villabanez.sedelectronica.es/info.0 | espublico gestiona (Wicket) |
| Tablón de anuncios | https://villabanez.sedelectronica.es/board/ | ~9 anuncios visibles (ago 2026) |
| Catálogo de trámites | https://villabanez.sedelectronica.es/dossier/.0 | Lento (>60 s); catálogo estándar CyL |
| Transparencia | https://villabanez.sedelectronica.es/transparency/ | Sección 7 «Urbanismo…» con 61 documentos |
| PlanPublica — PLAU | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=47&municipio=195 | 3 documentos |
| PlanPublica — PLAI | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=47&municipio=195 | 0 activos (sep 2026) |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=47195 | Mapa interactivo regional |

**Contacto:** C/ Hilario Vidarte s/n, 47329 Villabáñez · Tel. 983 520 801 · ayuntamiento@villabanez.gob.es

## 2. Urban planning — expedientes / planeamiento

### Instrumentos vigentes (PlanPublica PLAU)

| Subtipo | Fecha BOCYL | Título |
|---------|-------------|--------|
| PERI | 19/12/2001 | Plan Especial Reforma Interior «Dehesa de Peñalba» (CTU 140/99) |
| NUM | 01/06/2007 | Normas Urbanísticas Municipales |
| PERI | 16/12/2016 | Operaciones jurídicas complementarias al PERI Dehesa de Peñalba |

### Cómo se listan

- **PlanPublica:** tabla HTML con `doOpen(cDocId)`, fechas, subtipo (NUM/PERI), enlace PDF.
- **Tablón sede:** tabla Wicket con `preview-document/{uuid}`; sin paginación clara.
- **Transparencia:** árbol de carpetas (61 docs en sección urbanismo); requiere navegación AJAX Wicket.

### Endpoints útiles

```
GET https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=47&municipio=195
GET https://servicios.jcyl.es/PlanPublica/openDocumento.do?cDocId={id}
```

Códigos PlanPublica: **provincia=47** (Valladolid), **municipio=195** (Villabáñez).

## 3. Building licenses — tablón, sede, etc.

### Tablón de anuncios

Columnas: `Documento | Expediente | Procedimiento | Categoría | Descripción | Fecha`.

Anuncios recientes (2025–2026): cobranza IAE, bando limpieza de solares, presupuesto participativo,
modificación presupuestaria venta de parcelas. **Sin licencias de obra** con coordenadas.

### Catálogo de trámites (espublico estándar CyL)

Trámites informativos relevantes (UUIDs compartidos con otros municipios espublico):

| Trámite | Ruta |
|---------|------|
| Declaración Responsable o Comunicación en Materia Urbanística | `/catalog/t/5d383e20-32a5-4fcf-8725-e51c51e83e6a` |
| Solicitud de Licencia o Autorización Urbanística | `/catalog/t/15fabacb-83b1-47d1-b435-508245672051` |
| Solicitud de Modificación o Renuncia de Licencia Urbanística | `/catalog/t/a3c783fb-bb19-4ea3-b40f-0072d69aebae` |
| Solicitud de Licencia de Ocupación | `/catalog/t/b834b3fa-3690-4626-9c92-d82669d6f26f` |
| Solicitud de Certificado o Informe Urbanístico | `/catalog/t/e247f7c3-b1ff-42ef-8b7d-5195c14e9bbf` |
| Modificación del Planeamiento de Desarrollo | `/catalog/t/6e8237a3-0b83-469d-b0ad-70159b9a9c26` |
| Planeamiento General (Modificación) | `/catalog/t/96514574-aca1-40e1-a800-e06485e6d016` |
| Solicitud de Actuación Urbanística | `/catalog/t/f91e4a50-d23d-45c1-a19b-b148da37c59f` |

**No existe** dataset ni visor de licencias concedidas georreferenciadas.

## 4. CMS / tecnología

| Componente | Stack |
|------------|-------|
| Sede electrónica | **espublico gestiona** (`com.espublico.expedientes.*`) sobre **Apache Wicket** |
| Web corporativa | WordPress / portal Diputación Valladolid (inestable) |
| Planeamiento regional | **PlanPublica** JSP (Junta CyL) |
| GIS regional | **GeoServer** IDECyL + visor **SiUR** |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 polígono NUM municipal
  - WFS `urbanismo:plau_cyl_sectores` — 5 sectores SNC (ej. SNC-01 C/Arroyo Los Charcos)
  - SiUR visor regional `id=47195` (no API scrapeable directa)
- **Estrategia:** ingestar geometría desde WFS por municipio; cruzar códigos de sector del título
  PLAU (PERI, SNC) con `plau_cyl_sectores`; NUM hereda polígono de `plau_cyl_instrumentos_ambito`.
- **Limitaciones:** tablón y licencias sin GIS; transparencia solo PDFs; web corporativa con timeout.

### WFS — ejemplo

```
GET https://idecyl.jcyl.es/geoserver/urbanismo/wfs
  ?service=WFS&version=2.0.0&request=GetFeature
  &typeNames=urbanismo:plau_cyl_sectores
  &outputFormat=application/json&srsName=EPSG:4326
  &CQL_FILTER=n_mun='Villabáñez'
```

## Limitaciones

- `/dossier/.0` puede timeout (>60 s) sin sesión previa.
- Tablón: ventana corta (~9 filas), sin API.
- Licencias: solo trámites informativos, no concesiones históricas.
- Web `villabanez.es` no fiable para scrape automatizado.

## Estrategia adapter

1. **WFS IDECyL** → sectores + ámbito NUM con `geom_geojson`.
2. **PlanPublica PLAU** → 3 instrumentos con enlace PDF.
3. **Tablón sede** → filtrar keywords urbanismo (modificación presupuestaria parcelas, bandos).
4. **Catálogo trámites** → licencias/proyectos informativos (UUIDs estándar espublico).
5. **IDs:** `villabanez-{lic|proy}-{sha256[:14]}`.
