# Gomecello — investigación portal ayuntamiento

**Municipio:** Gomecello (provincia Salamanca, Castilla y León)  
**Fecha:** 2026-09-17  
**BOCYL (referencia):** 1 aviso (modificación puntual NUM, ago 2026)  
**INE:** 37121

## Resumen

Gomecello dispone de **web corporativa WordPress** (`gomecello.es`, redirige a sede) y **sede electrónica espublico gestiona** (`gomecello.sedelectronica.es`). El planeamiento urbanístico vigente (NUM + sectores UNC + plan parcial industrial) está centralizado en **PlanPublica / SiuCyL** (Junta de Castilla y León). No hay visor urbanístico municipal ni listado público de concesiones de licencias georreferenciadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web corporativa | http://gomecello.es | WordPress; timeouts SSL frecuentes (>60 s) |
| Urbanismo (WP) | http://gomecello.es/el-ayuntamiento/urbanismo/ | Timeout en agente; sección informativa |
| Sede electrónica | https://gomecello.sedelectronica.es/info | Redirige a `/info` |
| Tablón de anuncios | https://gomecello.sedelectronica.es/board/ | Responde 200; **tabla vacía** (ago 2026) |
| Catálogo de trámites | https://gomecello.sedelectronica.es/dossier/.0 | Bucle de redirección 302 |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=121 | 9 documentos |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=121 | Sin documentos activos |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=37121 | Mapa interactivo regional |
| IDECyL WFS urbanismo | https://idecyl.jcyl.es/geoserver/urbanismo/wfs | Capas PLAU por municipio |

**Contacto:** Plaza de la Constitución 5, 37420 Gomecello · Tel. 923 35 00 52 · aytogomecello@gmail.com

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **NUM** (Normas Urbanísticas Municipales), aprobación definitiva **30/04/2012**.
- Múltiples **modificaciones puntuales** de las NUM (2014, 2015, 2017, 2019, 2025).
- **Plan Parcial del Sector Industrial Sur-2I** (PPI, 2014).
- Sectores **UNC1–UNC4** en suelo urbanizable (WFS IDECyL).

### Listado PlanPublica (PLAU) — cómo se presentan

Página HTML con tabla `#listado` ordenable. Cada fila incluye tipo (PU), subtipo (NUM/PPI/NS), fechas y título. Enlaces PDF vía `openDocumento.do?cDocId={id}`.

**Documentos identificados (sep 2026):**

| Fecha pub. | Subtipo | Título |
|------------|---------|--------|
| 14/04/2010 | NS | Modificación II objetivo B ordenación detallada sector E2 Ur-2 de Cilloruelo |
| 30/04/2012 | NUM | Normas Urbanísticas Municipales |
| 02/04/2014 | NUM | Modificación de las NUM — parámetros en suelo rústico |
| 30/01/2015 | NUM | Corrección de errores de las NUM |
| 26/09/2017 | NUM | Corrección error material (calles Cilloruelo) |
| 14/03/2019 | NUM | Modificación nº 2 — condiciones en suelo rústico |
| 17/10/2014 | PPI | Plan Parcial del Sector Industrial Sur-2I |
| 11/06/2025 | NUM | Modificación nº 3 — cambio de ordenanza en suelo urbano consolidado |

### Licencias de obra

- El **tablón de anuncios** de la sede está vacío (sin concesiones publicadas).
- El catálogo de trámites (`/dossier/.0`) no es accesible por bucle de redirección.
- Se ingestan **páginas informativas de trámites** genéricos de la sede (licencia, comunicación previa, etc.) como referencia, no como concesiones.

## 3. Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 polígono MultiPolygon (ámbito NUM)
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — 4 polígonos (UNC1–UNC4)
  - IDECyL WFS `urbanismo:plau_cyl_planes_parciales` — 0 features
  - SiUR visor regional: https://idecyl.jcyl.es/siur/index.html?id=37121
- **Estrategia:** query WFS por `n_mun = 'Gomecello'`; enriquecer proyectos PLAU con polígono NUM o sector UNC por código en título.
- **Limitaciones:**
  - Sin visor municipal propio ni API de expedientes con geometría.
  - Web corporativa inaccesible por timeouts SSL.
  - Tablón sin licencias → sin geometría de licencias.
  - Documentos PLAU son PDFs sin coordenadas embebidas; geometría solo vía WFS regional.

## 4. Limitaciones generales

- `gomecello.es` inaccesible de forma fiable (SSL handshake timeout).
- Sede `/info.0` y `/dossier/.0` con bucles de redirección; solo `/board/` responde.
- Sin dataset de licencias georreferenciadas.
- Paginación PLAU no necesaria (9 filas).

## 5. Adapter

- Módulo: `municipio/adapters/gomecello.py`
- Fuentes: PLAU JCYL + IDECyL WFS + tablón sede + catálogo trámites (fallback)
- IDs estables: `gomecello-{lic|proy}-{sha256[:14]}`
