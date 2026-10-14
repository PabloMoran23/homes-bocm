# Peromingo — investigación portal ayuntamiento

**Municipio:** Peromingo (provincia Salamanca, Castilla y León)  
**Fecha:** 2026-09-28  
**BOCYL (referencia):** 1 aviso  
**INE:** 37253 (PlanPublica provincia 37, municipio **253**) | **DIR3:** L01372513

## Resumen

No hay web corporativa municipal accesible (`www.peromingo.es` sin respuesta útil). La **sede electrónica**
espublico gestiona (`https://peromingo.sedelectronica.es`) responde con tablón operativo pero **sin filas**
de anuncios urbanísticos (sep/2026). Las rutas `info.0` / `dossier/.0` provocan bucle de redirección;
el subdominio INE `37253.sedelectronica.es` muestra página «Sede Electrónica Indeterminada».

El planeamiento (NUM, modificaciones, GU) está publicado en **PlanPublica** (Junta CYL). La geometría del
término y sectores aparece en **IDECyL WFS** (`plau_cyl_instrumentos_ambito`, `plau_cyl_sectores`).

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Sede (nombre) | https://peromingo.sedelectronica.es/ | espublico gestiona, tablón vacío |
| Sede (INE) | https://37253.sedelectronica.es/ | «Indeterminada» |
| Tablón | https://peromingo.sedelectronica.es/board | Sin `preview-document` |
| PlanPublica — archivo (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=253 | 3 documentos (NUM + modificación UR-3 + GU) |
| PlanPublica — info pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=253 | Sin IP activa reciente |
| SiuCyL / SiUR | https://idecyl.jcyl.es/siur/index.html?id=37253 | Visor regional |
| Contacto | Calle Puente 2, 37791 · Tel. 923 165 162 | Directorio ayuntamientos |

## 2. Planeamiento / expedientes

### PlanPublica (PLAU)

Tabla HTML con enlaces `doGoBoletin('cDocId', …)` → `openDocumento.do?cDocId=…`.

Documentos identificados (sep/2026):

| cDocId | Subtipo | Título (resumen) |
|--------|---------|------------------|
| 282285 | NUM | NORMAS URBANÍSTICAS MUNICIPALES |
| 285752 | NUM | Modificación NN.UU. sector **UR-3** y plan parcial sector UR-3 |
| 290752 | GU | (documentación general urbanística) |

### IDECyL WFS

- `urbanismo:plau_cyl_instrumentos_ambito` — 1 feature (`n_mun=Peromingo`, polígono término/instrumento).
- `urbanismo:plau_cyl_sectores` — 1 sector (`SUR-1` / «Colada de las eras») con geometría.

Listado HTML de expedientes en sede: **no disponible** (tablón vacío).

## 3. Licencias de obra

No hay concesiones publicadas en tablón. El catálogo de trámites en `/dossier` (con sesión espublico) expone
páginas informativas de licencias/comunicaciones urbanísticas — el adapter las incluye como filas tipo «trámite licencia»
(sin `fecha_concesion`), patrón Pozuelo/Lumbrales.

## Geometría / visor

- **geometry_status:** partial
- **Fuentes:**
  - WFS IDECyL `urbanismo:plau_cyl_instrumentos_ambito` — filtro `n_mun='Peromingo'` → polígono municipal.
  - WFS `urbanismo:plau_cyl_sectores` — sector SUR-1 con polígono.
  - SiuCyL: https://idecyl.jcyl.es/siur/index.html?id=37253
- **Estrategia:** Proyectos PLAU subtipo NUM/GU enriquecidos con polígono del instrumento; títulos con **UR-3** intentan sector WFS; filas WFS de sectores incluyen geometría directa.
- **Limitaciones:** Tablón sin licencias; visor municipal inexistente; dossier con redirect loop; sector UR-3 puede no coincidir con código WFS (SUR-1).

## 4. Adapter

Patrón **Moríñigo / Valverdón** (`municipio/adapters/morinigo.py`):

- `backfill_proyectos`: WFS + PLAU + PLAI + tablón (vacío).
- `backfill_licencias`: tablón + catálogo (vacío).
- Geometría: `_attach_geometry` + WFS instrumentos/sectores.
