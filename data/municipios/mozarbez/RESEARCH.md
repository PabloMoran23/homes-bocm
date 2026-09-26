# Mozárbez — investigación portal ayuntamiento

**Municipio:** Mozárbez (provincia Salamanca, Castilla y León)  
**Fecha:** 2026-09-25  
**BOCYL (referencia):** 1 aviso  
**INE:** 37206

## Resumen

Mozárbez **no tiene web corporativa** (`mozarbez.es` / `www.mozarbez.es` no resuelven). La publicación municipal pasa por la
**sede electrónica espublico gestiona** (`mozarbez.sedelectronica.es`). El planeamiento está en **PlanPublica / SiuCyL**
(provincia 37, municipio 206). No hay listado público de concesiones de licencias georreferenciadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Sede electrónica | https://mozarbez.sedelectronica.es/info | Redirección desde `/` |
| Tablón de anuncios | https://mozarbez.sedelectronica.es/board/ | HTML Wicket, ~3 anuncios (ago 2026) |
| Catálogo trámites | https://mozarbez.sedelectronica.es/dossier/.0 | Timeout frecuente en agente; fallback a páginas estándar espublico |
| PlanPublica PLAU | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=206 | 5+ documentos de planeamiento |
| PlanPublica PLAI | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=206 | Información pública |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=37206 | Mapa regional JCYL |
| IDECyL WFS urbanismo | https://idecyl.jcyl.es/geoserver/urbanismo/wfs | Capas PLAU CYL filtradas por `n_mun='Mozárbez'` |

## 2. Urbanismo — cómo se listan expedientes

### Tablón (sede)

Tabla HTML `#id10` con filas `preview-document/{uuid}`. Columnas: documento, expediente, procedimiento, categoría, descripción, fecha.
En la muestra actual predominan anuncios generales (incendios, cobranza, telecomunicaciones), no urbanismo.

### PlanPublica (PLAU)

Tabla HTML `#listado` con filas `doOpen(cDocId, código)`. Instrumentos históricos y **NUM** vigente identificados, p. ej.:

- `277920` — Normas subsidiarias de planeamiento municipal (1995)
- `283532` — **NUM** (Normas Urbanísticas Municipales)
- Modificaciones puntuales (`277921`, `282432`, `282448`, …)

PDF: `https://servicios.jcyl.es/PlanPublica/openDocumento.do?cDocId={id}`

### Licencias

No hay tablón de concesiones de obra. El adapter expone **páginas informativas** de trámites de licencia del catálogo espublico
(mismo patrón que Valverdón / Pelabravo).

## 3. Geometría / visor

- **geometry_status:** partial
- **Fuentes:**
  - WFS GeoServer JCYL `urbanismo:plau_cyl_instrumentos_ambito` — polígono del instrumento (NUM) con `n_mun='Mozárbez'`, `c_mun=37206`
  - WFS `urbanismo:plau_cyl_planes_parciales` y `urbanismo:plau_cyl_sectores` — sectores/planes parciales si existen
  - SiUR `https://idecyl.jcyl.es/siur/index.html?id=37206` — visor regional (no API directa por expediente de tablón)
- **Estrategia:** ingestar features WFS en `backfill_proyectos`; enriquecer filas PLAU/tablón con `_attach_geometry` vía código de sector o polígono NUM (`subtipo=NUM`).
- **Limitaciones:** tablón sin coords; licencias sin geometría; dossier lento; web municipal inexistente.

## 4. Limitaciones técnicas

- Certificado sede: usar `insecure_ssl: true` en manifest (patrón CYL).
- `dossier/.0` puede tardar >60 s o fallar — no bloquea si PLAU+WFS responden.
- User-Agent identificable recomendado (`poc-bocm-mozarbez/1.0`).
