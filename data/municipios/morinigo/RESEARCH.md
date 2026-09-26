# Moríñigo — investigación portal ayuntamiento

**Municipio:** Moríñigo (provincia Salamanca, Castilla y León)  
**Fecha:** 2026-09-25  
**BOCYL (referencia):** 1 aviso  
**INE:** 37206 (provincia 37, municipio 206) | **DIR3:** L01372066

## Resumen

Moríñigo **no tiene web corporativa** accesible (`*.morinigo.es`, `aytomorinigo.es` sin DNS/HTTP).
La sede electrónica espublico (`37206.sedelectronica.es`, alias `aytomorinigo.sedelectronica.es`)
devuelve la página **«Sede Electrónica Indeterminada»** en tablón, dossier e info: no hay tablón
operativo ni catálogo de trámites scrapeable.

El planeamiento urbanístico histórico (NS / modificaciones puntuales) está en **PlanPublica**
(Junta CYL). La geometría del término municipal aparece en **IDECyL WFS** (`plau_cyl_instrumentos_ambito`).

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Sede (subdominio INE) | https://37206.sedelectronica.es/ | HTTP 200 pero contenido «Indeterminada» |
| Sede alias | https://aytomorinigo.sedelectronica.es/ | Mismo estado |
| Tablón | https://37206.sedelectronica.es/board/ | Sin filas `preview-document` |
| PlanPublica — archivo (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=206 | 5 documentos NS (1995–2007) |
| PlanPublica — info pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=206 | 2 entradas (sin IP activa reciente) |
| SiuCyL / SiUR | https://idecyl.jcyl.es/siur/index.html?id=37206 | Visor regional |
| Ficha Diputación | http://www.salamanca.es/...?codMunicipio=206 | Datos municipales |

**Contacto:** Plaza Constitución 1, 37337 · Tel. 923 360 650 · aytomorinigo@hotmail.com

## 2. Planeamiento / expedientes

### PlanPublica (PLAU)

Tabla HTML `#listado` con columnas Libro / Tipo / fechas / título. Enlaces:

- `openDocumento.do?cDocId={id}`
- `openDocuIndice.do?cDocId={id}`

Documentos identificados (sep 2026):

| cDocId | Subtipo | Fecha pub. | Título |
|--------|---------|------------|--------|
| 277920 | NS | 06/03/1995 | NORMAS SUBSIDIARIAS DE PLANEAMIENTO MUNICIPAL |
| 277921 | NS | 04/06/1999 | MODIFICACION PUNTUAL |
| 282432 | NS | 23/08/2004 | MODIFICACIÓN PUNTUAL N.º II… |
| 282448 | NS | 29/09/2004 | MODIFICACIÓN PUNTUAL, EXPTE. 362/03 |
| (5.º doc) | NS | 20/09/2007 | CORRECCIÓN DE ERRORES DE LAS NN.SS. |

No hay sectores/PE/PAU recientes en el listado; municipio pequeño (~87 hab.) con instrumento NS histórico.

## 3. Licencias de obra

No hay publicación de concesiones en tablón (sede inactiva). Las licencias no aparecen en PlanPublica.
El adapter devuelve **lista vacía** de licencias (`min_rows: 0` en validación).

## Geometría / visor

- **geometry_status:** partial
- **Fuentes:**
  - WFS IDECyL `urbanismo:plau_cyl_instrumentos_ambito` — filtro `n_mun='Moríñigo'` o `c_mun='37206'` → 1 `MultiPolygon` (ámbito NUM/NS municipal).
  - Capas `plau_cyl_sectores` / `plau_cyl_planes_parciales`: **0 features** para este municipio.
  - SiuCyL visor: https://idecyl.jcyl.es/siur/index.html?id=37206 (sin API expediente→polígono por fila de tablón).
- **Estrategia:** Enriquecer proyectos PLAU subtipo `NS` con polígono del instrumento vía WFS; resto sin geometría fina.
- **Limitaciones:** Sede indeterminada; sin visor municipal; licencias sin coords; sectores ausentes en WFS.

## 4. Adapter

Patrón **Valverdón** (`municipio/adapters/valverdon.py`):

- `backfill_proyectos`: PLAU + PLAI + WFS instrumentos.
- `backfill_licencias`: intento tablón (vacío) + catálogo (vacío).
- Geometría: `_attach_geometry` + WFS NUM/NS.
