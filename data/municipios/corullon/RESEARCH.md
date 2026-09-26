# Corullón — investigación portal ayuntamiento

**Municipio:** Corullón (provincia León, Castilla y León)  
**Fecha:** 2026-09-13  
**BOCYL (referencia):** 1 aviso  
**INE:** 24059 | **CIF:** P2406100D

## Resumen

Corullón **no dispone de web corporativa operativa** (`www.corullon.es` sin dominio;
`ayuntamientodecorullon.org` muestra parking de registrador). La administración digital pasa por la
**sede electrónica espublico gestiona** (`corullon.sedelectronica.es`). El planeamiento urbanístico
vigente (NUM + modificaciones + estudio de detalle SUNC-6) está en **PlanPublica / SiuCyL** (Junta
de Castilla y León). No hay visor urbanístico municipal ni listado público de licencias concedidas
con coordenadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web corporativa (inactiva) | http://ayuntamientodecorullon.org | Parking page (Spaceship) |
| Sede electrónica (inicio) | https://corullon.sedelectronica.es/info.0 | Requiere cookie de sesión |
| Tablón de anuncios | https://corullon.sedelectronica.es/board/ | 5 anuncios visibles (ago 2026) |
| Catálogo de trámites | https://corullon.sedelectronica.es/dossier/.0 | ~105 trámites; requiere cookie |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=24&municipio=061 | 8 documentos |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=24&municipio=061 | Sin documentos activos (sep 2026) |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=24059 | Mapa interactivo regional |

**Contacto:** Plaza del Ayuntamiento, 1, 24514 Corullón · Tel. 987 542 640 · ayuntamiento@corullon.es

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **NUM** (Normas Urbanísticas Municipales), aprobación definitiva **03/02/2010** (BOCYL 07/07/2010).
- Sectores SU-NC 1, 2 y 3 en suelo urbano no consolidado (residencial).
- Estudio de detalle **SUNC-6** aprobado definitivamente (2011).

### Listado PlanPublica (PLAU)

Página HTML con tabla ordenable. Documentos identificados (sep 2026):

| Fecha | Subtipo | Título |
|-------|---------|--------|
| 01/06/2004 | NUM | NORMAS URBANÍSTICAS MUNICIPALES |
| 29/10/2008 | NUM | MODIFICACIÓN PUNTUAL Nº 1 DE LAS NUM |
| 13/08/2010 | NUM | MODIFICACIÓN PUNTUAL Nº 3 DE LAS NUM |
| 07/04/2009 | ED | ESTUDIO DE DETALLE DEL SECTOR SUNC-6 |
| 06/07/2011 | ED | ACUERDO APROBACIÓN DEFINITIVA ESTUDIO DE DETALLE C/ REAL Nº 3 |
| 06/07/2011 | ED | ACUERDO APROBACIÓN DEFINITIVA ESTUDIO DE DETALLE SUNC-6 |
| 15/04/2013 | NUM | MODIFICACIÓN PUNTUAL Nº 4 DE LAS NUM |
| 15/11/2017 | NUM | MODIFICACIÓN Nº 5 DE LAS NUM (apicicultura) |

Códigos PlanPublica: **provincia=24** (León), **municipio=061** (Corullón).

## 3. Building licenses — tablón, sede, etc.

### Tablón de anuncios (`/board/`)

Anuncios recientes (jun–ago 2026): cuenta general, subvenciones juventud/ELEX/PLANIEL, cobranza IAE.
**Sin licencias de obra** en la ventana visible. PDFs en `preview-document/{uuid}`.

### Catálogo de trámites (`/dossier/.0`)

Trámites informativos relevantes (mismos UUIDs espublico que otros municipios CyL):

| Trámite | URL |
|---------|-----|
| Declaración Responsable o Comunicación en Materia Urbanística | `/catalog/t/5d383e20-32a5-4fcf-8725-e51c51e83e6a` |
| Solicitud de Licencia o Autorización Urbanística | `/catalog/t/15fabacb-83b1-47d1-b435-508245672051` |
| Solicitud de Licencia de Ocupación | `/catalog/t/b834b3fa-3690-4626-9c92-d82669d6f26f` |
| Modificación del Planeamiento de Desarrollo | `/catalog/t/6e8237a3-0b83-469d-b0ad-70159b9a9c26` |
| Planeamiento General (Modificación) | `/catalog/t/96514574-aca1-40e1-a800-e06485e6d016` |

**No existe** dataset ni visor de licencias concedidas con coordenadas.

## 4. GIS / geometría

| Fuente | URL | Contenido Corullón |
|--------|-----|-------------------|
| WFS SIUCyL sectores | `urbanismo:plau_cyl_sectores` | **3 polígonos** SU-NC 1, 2, 3 |
| WFS instrumentos | `urbanismo:plau_cyl_instrumentos_ambito` | **1 polígono** NUM municipal |
| WFS planes parciales | `urbanismo:plau_cyl_planes_parciales` | 0 features |
| SiUR visor | `https://idecyl.jcyl.es/siur/index.html?id=24059` | Visor regional |

**No hay:** visor urbanístico municipal propio, ArcGIS municipal, WFS local.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS IDECyL `plau_cyl_sectores` (SU-NC 1–3) y `plau_cyl_instrumentos_ambito` (ámbito NUM).
- **Estrategia:** extraer `SUNC-6`, `SU-NC n` del título PLAU → cruzar con WFS; NUM usa polígono
  municipal completo; fallback centroide `[42.581, -6.818]` + jitter.
- **Limitaciones:** licencias y tablón sin GIS; web corporativa inactiva; sede dossier lento sin cookie.

## Limitaciones

- Sin web municipal operativa.
- Tablón: ventana corta, sin licencias urbanísticas.
- Catálogo: formularios, no resoluciones históricas.
- Geometría solo a nivel sector/instrumento (no por expediente individual en sede).

## Estrategia adapter

1. **PlanPublica PLAU** → parsear tabla HTML (`openDocumento.do`, fechas, títulos).
2. **WFS IDECyL** → geometría por sector (`plau_cyl_sectores`) e instrumento NUM.
3. **Tablón sede** (`/board/`) → filtrar keywords urbanismo/licencia.
4. **Catálogo dossier** → licencias informativas (`/catalog/t/{uuid}`).
5. **IDs:** `corullon-{lic|proy}-{sha256[:14]}`.
