# Puente del Congosto — investigación portal ayuntamiento

**Municipio:** Puente del Congosto (provincia Salamanca, Castilla y León)  
**Fecha:** 2026-10-14  
**BOCYL (referencia):** 1 aviso  
**INE:** 37261 (PlanPublica municipio 261, provincia 37)

## Resumen

El ayuntamiento publica noticias en **WordPress** (`http://puentedelcongosto.es`), pero desde redes
externas el sitio suele **no responder** (timeout). La **sede electrónica espublico**
(`https://puentedelcongosto.sedelectronica.es`) está operativa: catálogo de trámites e
instancia general, pero el **tablón de anuncios no tiene filas** con documentos urbanísticos
(o licencias) en el momento de la investigación.

El planeamiento (NUM y modificaciones) se consulta en **PlanPublica** (Junta de Castilla y León).
La geometría de instrumentos y sectores está en **IDECyL WFS** (`plau_cyl_*`).

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web municipal | http://puentedelcongosto.es/ | WordPress; timeout frecuente |
| Sede electrónica | https://puentedelcongosto.sedelectronica.es/ | espublico gestiona |
| Tablón | https://puentedelcongosto.sedelectronica.es/board | Sin anuncios con `preview-document` |
| Trámites | https://puentedelcongosto.sedelectronica.es/dossier | Catálogo general |
| PlanPublica — archivo (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=261 | 4 documentos NUM (2013–2026) |
| PlanPublica — info pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=261 | Sin IP activa relevante |
| SiuCyL / SiUR | https://idecyl.jcyl.es/siur/index.html?id=37261 | Visor regional |

**Contacto:** Plaza Mayor 2, 37748 · Tel. 923 15 22 63 · aytopuentedelcongosto@hotmail.com

## 2. Planeamiento / expedientes

### PlanPublica (PLAU)

Tabla HTML con columnas Libro / Tipo / fechas / título. Enlaces `openDocumento.do?cDocId={id}`.

Documentos identificados (oct 2026):

| Subtipo | Fecha pub. | Título (resumen) |
|---------|------------|------------------|
| NUM | 04/07/2013 | Normas Urbanísticas Municipales |
| NUM | 22/08/2018 | Modificación NUM — parcela Calle Los Bolos |
| NUM | 23/02/2024 | Modificación nº 2 NUM — uso ganadero intensivo / suelo rústico |
| NUM | 24/02/2026 | Fallo sentencia recurso 438/2024 (mod. nº 2 NUM) |

### IDECyL WFS

- `urbanismo:plau_cyl_instrumentos_ambito` — 1 feature (ámbito NUM municipal, ~34 km²).
- `urbanismo:plau_cyl_sectores` — 7 sectores con polígonos.
- `urbanismo:plau_cyl_planes_parciales` — sin features para este municipio en la consulta por `n_mun`.

## 3. Licencias de obra

No hay concesiones publicadas en el tablón de la sede. PlanPublica no lista licencias de obra.
El adapter devuelve **lista vacía** de licencias (válido con `min_rows: 0`).

## Geometría / visor

- **geometry_status:** available
- **Fuentes:**
  - WFS IDECyL `urbanismo:plau_cyl_instrumentos_ambito` — filtro `n_mun='Puente del Congosto'` → polígono del ámbito NUM.
  - WFS `urbanismo:plau_cyl_sectores` — 7 polígonos de sectores (enlace por código de sector en título PLAU si aplica).
  - SiuCyL: https://idecyl.jcyl.es/siur/index.html?id=37261
- **Estrategia:** Ingesta WFS en `backfill_proyectos`; enriquecer filas PLAU subtipo `NUM` con polígono del instrumento; sectores vía `_wfs_sector_geometry` si el texto menciona código.
- **Limitaciones:** Tablón sin licencias; web municipal inestable; sin visor municipal propio (solo regional).

## 4. Adapter

Patrón **Moríñigo / Valverdón** (`municipio/adapters/puente_del_congosto.py`):

- `backfill_proyectos`: WFS + PLAU + tablón/catálogo (si aparecen filas).
- `backfill_licencias`: tablón + trámites (vacío esperado).
- Geometría: polígonos WFS + `_attach_geometry` para NUM/sectores.
