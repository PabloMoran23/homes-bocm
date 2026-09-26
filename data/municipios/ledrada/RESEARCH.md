# Ledrada — investigación portal ayuntamiento

**Municipio:** Ledrada (provincia Salamanca, Castilla y León)  
**Fecha:** 2026-09-21  
**BOCYL (referencia):** 1 aviso  
**INE:** 37171 | **PlanPublica municipio:** 171

## Resumen

Ledrada no dispone de web corporativa accesible (`www.ledrada.es` sin resolución DNS desde CI).
La presencia digital municipal pasa por la **sede electrónica espublico gestiona**
(`ledrada.sedelectronica.es`). El planeamiento urbanístico vigente (NUM revisión 2020 + sectores
SU-NC + polígono industrial Las Eras) está centralizado en **PlanPublica / SiuCyL** (Junta de
Castilla y León). No hay listado público de concesiones de licencias georreferenciadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Sede electrónica (inicio) | https://ledrada.sedelectronica.es/info.0 | Redirige desde `/` |
| Tablón de anuncios | https://ledrada.sedelectronica.es/board | Vacío (ago 2026) |
| Catálogo de trámites | https://ledrada.sedelectronica.es/dossier/.0 | 114 trámites; `/dossier.0` provoca redirect loop |
| Transparencia | https://ledrada.sedelectronica.es/transparency/ | Sin documentos urbanismo |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=171 | 5 documentos |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=171 | Sin documentos activos |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=37171 | Mapa interactivo regional |
| Web corporativa | https://www.ledrada.es | Inaccesible (DNS/timeout CI) |

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **NUM** (Normas Urbanísticas Municipales — Revisión), aprobación definitiva **22/07/2020**
  (`cDocId=296814`, BOCYL 23/09/2020).
- Sectores SU-NC: UNC-I1…UNC-I4, UNC-R1, UNC-R2 (industrial/residencial).
- Polígono industrial **Las Eras** (suelo urbanizable, sectores Las Eras 1 y Las Eras 2).
- Proyecto histórico **Sector E** (PAU 2013, `cDocId=289522`) y convenio urbanístico asociado
  (`cDocId=296869`).
- Plan Regional de Ámbito Territorial OTPRAT_31 para desarrollo polígono industrial Las Eras
  (`cDocId=301837`, 2026).

### Listado PlanPublica (PLAU)

Página HTML con tabla ordenable. Campos: libro (PU/GU/CU/OT), subtipo (NUM/PAU/CN_UR/PRAT),
fecha publicación, título, enlace `openDocumento.do?cDocId={id}`.

**Documentos identificados (sep 2026):**

| cDocId | Tipo | Fecha | Título |
|--------|------|-------|--------|
| 289522 | GU PAU | 27/05/2013 | Proyecto de actuación Sector "E" |
| 296869 | CU CN_UR | 07/05/2020 | Convenio urbanístico Sector E |
| 296814 | PU NUM | 23/07/2020 | Normas Urbanísticas Municipales (Revisión) |
| 301837 | OT PRAT | 06/08/2026 | OTPRAT_31 polígono industrial Las Eras |
| 301851 | OT PRAT | 06/08/2026 | Corrección errores OTPRAT_31 Las Heras |

## 3. Licencias

- Tablón de anuncios **vacío** (sin concesiones publicadas).
- Catálogo sede con trámites informativos de licencia urbanística, ocupación, DR/comunicación
  previa, certificados urbanísticos (UUIDs espublico estándar).
- Sin dataset ni visor de licencias con coordenadas.

## 4. Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 feature (NUM, MultiPolygon municipio)
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — 8 sectores (UNC-I1…UNC-R2, Las Eras 1/2)
  - SiUR visor: `https://idecyl.jcyl.es/siur/index.html?id=37171`
- **Estrategia:** query WFS por `n_mun='Ledrada'`; enriquecer PLAU por código sector (UNC-*, Las Eras)
  o polígono NUM para documentos sin sector explícito.
- **Limitaciones:**
  - Sector E (PAU 2013) no aparece como polígono en WFS actual (solo NUM + 8 sectores SU-NC/Las Eras).
  - Tablón sin anuncios → licencias sin geometría.
  - `www.ledrada.es` inaccesible.

## 5. Adapter

Patrón CYL/Salamanca (espublico + PlanPublica + IDECyL WFS), similar a Valverdón/Alba de Tormes:

1. WFS → instrumentos + sectores con `geom_geojson`
2. PlanPublica PLAU → proyectos PDF con geometría por sector/NUM
3. Catálogo trámites sede → licencias informativas (sin coords)
4. Tablón → vacío (monitorizado)
