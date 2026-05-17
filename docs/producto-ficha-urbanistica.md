# Producto: qué está pasando en tu zona (Madrid)

Agregador de información urbanística para **vecinos** y **profesionales**.  
No promete un total municipal de viviendas; informa por **ámbito / expediente / parcela**.

Última revisión: 2026-05-17

---

## Pantallas

| # | Pantalla | Ruta actual / propuesta | Usuario |
|---|----------|-------------------------|---------|
| 1 | **Mapa SIGMA** | `/explore` (Madrid) | “¿Qué hay cerca?” |
| 2 | **Ficha expediente** | `/sigma/[slug]` | “¿Qué es esta actuación?” |
| 3 | **Ficha parcela / edificio** | `/ubicacion/[ndp]` | “¿Qué pasa en mi dirección?” |
| 4 | **Zona (futuro)** | `/madrid/zona?…` o bbox en mapa | “¿Qué se tramita en el barrio?” |

---

## 1. Mapa SIGMA (explorador)

### Qué ve el usuario
- Polígonos de expedientes (planeamiento, gestión, urbanización, IP).
- Color o badge por **fase** y filtros (≥2020, con enlace visor, con BOCM).
- Popup al clic con resumen mínimo + enlace a ficha.

### Campos del popup (popup mínimo)

| Campo UI | Descripción | Fuente | Disponibilidad |
|----------|-------------|--------|----------------|
| Título | Denominación del expediente | `madrid_ayto_expedientes_index` → `EXP_TX_DENOM` o visor `h1` | Casi siempre |
| Expediente | `135/2018/00716` | Índice / visor `grupo` | Siempre |
| Fase | Aprobación definitiva, IP… | `FAS_TX_DENOM` | A menudo |
| Tipo actuación | Plan parcial, ED, PE… | Inferido: denominación + `FIG_TX_ETIQ` | Heurística |
| **Viviendas** | Cifra o etiqueta | `sigma_expediente_metric` | **~17 % recientes; ver badge** |
| Badge cobertura | “Con análisis PDF” / “Solo catálogo” | `sigma_expediente_metric` existe o no | Siempre |
| Enlaces | Ficha portal, Visor ayuntamiento | `Enlace`, `visorUrl` | A menudo |

### Badges de viviendas (popup y ficha)

| Valor interno `genera_vivienda_nueva` | Texto vecino | Texto pro |
|--------------------------------------|--------------|-----------|
| `si` | “Incluye vivienda nueva” | “Programa edificatorio con cifra” |
| `probable_si` | “Posible obra nueva” | “Estimación / programa con viviendas” |
| `probable_sin_cifra` | “Puede haber obra; sin cifra” | “Edificabilidad sin nº de viv.” |
| `stock_existente_o_rehabilitacion` | “Rehabilitación / stock existente” | “No cuenta como vivienda nueva” |
| `no` | “Sin vivienda nueva (uso/catalogación)” | “PECUAU, catalogación, dotacional” |
| `desconocido` | “Viviendas: sin datos” | “Sin extracción PDF” |

| Si hay `num_viviendas_max` | Mostrar |
|---------------------------|---------|
| Sí | “Hasta **N** viviendas” + tooltip “Según [documento]” |
| No | Solo badge de tipo (tabla arriba) |

---

## 2. Ficha expediente (`/sigma/[slug]`)

Vista principal del producto. Pestañas actuales + **bloque nuevo “Qué implica”**.

### Bloque A — Cabecera (ya existe, mantener)

| Campo | Fuente |
|-------|--------|
| Título | visor `h1` / `EXP_TX_DENOM` |
| Subtítulo | visor `h2` / `FIG_TX_ETIQ` |
| Nº expediente | `expedienteGrupo` |
| Chips | IP / tramitados / BOCM enlazado |
| CTA | Visor municipal, BOCM si hay |

### Bloque B — KPIs (ampliar)

| KPI | Fuente | Notas |
|-----|--------|-------|
| Fase SIGMA | `FAS_TX_DENOM` | Existe |
| Último hito | `tramitacion[-1]` | Fecha + trámite |
| Documentos NTI | `ntiDocumentosTotal` / SQLite NTI | |
| **Viviendas** | `sigma_expediente_metric.num_viviendas_max` | Con disclaimer |
| **Superficie ámbito** | `sup_total_m2` | m² si existe |
| **Edificabilidad** | `sup_edificable_m2` | m² si existe |
| Tipo vivienda | `tipo_vivienda` | VPP, unifamiliar… |
| Confianza | `hechos_json[].confianza` | “Alta / estimación / IA” |

### Bloque C — “Qué implica” (texto fijo + datos)

Párrafo generado por plantilla según `familia_expediente`:

| `familia_expediente` | Mensaje tipo |
|---------------------|--------------|
| `estudio_detalle` | Ordenación de parcela/edificio; suele ir antes de licencias. |
| `plan_parcial` | Define reglas del sector (usos, alturas, edificabilidad). |
| `plan_especial` | Caso concreto (colonia, catalogación, regeneración…). |
| `modificacion_pgou` | Cambio puntual del Plan General (gran escala si MPG). |
| `pecuau` | Control de usos en edificio existente (locales, aforo). |
| `catalogacion` | Protección / cambio de régimen del edificio, no obra nueva masiva. |

### Bloque D — Fuentes y transparencia (nuevo)

| Campo | Fuente |
|-------|--------|
| Lista “Dato → PDF” | `sigma_expediente_metric.hechos_json` |
| PDFs analizados | `fuentes_pdf_json` / `sigma_pdf_metric` |
| Fecha extracción | `sigma_expediente_metric.updated_at` |
| Aviso legal | Texto fijo: “No es resolución vinculante; consultar documentos oficiales.” |

### Pestañas (ya existen)

| Pestaña | Contenido | Fuente |
|---------|----------|--------|
| Resumen | Metadatos catálogo | índice SIGMA |
| Tramitación | Timeline | `madrid_viso_expedientes` → `tramitacion[]` |
| Documentos | Lista NTI + descargas | `sigma-nti-linked.json` / SQLite `sigma_nti_document` |
| BOCM | Anuncios enlazados | `madrid-sigma-bocm-projects.json` |

### Mapa en ficha
- Polígono del expediente (geojson capa AD/IP).
- Mini leyenda: ámbito afectado.

---

## 3. Ficha parcela / edificio (`/ubicacion/[ndp]`)

Para el vecino que busca su dirección.

| Campo | Fuente | Notas |
|-------|--------|-------|
| Dirección | `ubicacion` / licencias | |
| Distrito, coords | SQLite ubicación | |
| **Expedientes SIGMA que intersectan** | Cruce espacial (pendiente mejorar) | Lista con enlace a ficha |
| **Licencias recientes** | `madrid_licencias` por NDP | Tipo, fechas, procedimiento |
| Resumen humano | Plantilla | “Hay X licencias desde 2020; Y expedientes de planeamiento afectan esta parcela.” |
| Sin cruce | Mensaje honesto | “No hay expediente SIGMA identificado en esta parcela.” |

No mostrar total de viviendas en parcela salvo que un expediente + métrica lo justifique.

---

## 4. Zona / barrio (futuro)

Agregación por **bbox**, distrito o clic en “ver actuaciones aquí”.

| Campo | Cálculo |
|-------|---------|
| Nº expedientes en área | Count geo dentro bbox |
| Nº en tramitación reciente | Filtro fase + año |
| Con señal de vivienda | `genera_vivienda_nueva` in (`si`, `probable_si`) |
| Lista ordenada | Por fecha último hito |
| **No sumar viviendas** en v1 | Mostrar “N actuaciones con cifra” + lista, evitar doble conteo |

---

## Mapa datos → sistemas

```
SIGMA índice (JSON)     → catálogo, fase, figura, fechas
madrid_viso_expedientes → tramitación, NTI árbol, URLs
madrid_nti_downloads/   → PDFs locales
sigma_expediente_metric → métricas agregadas + hechos
sigma_pdf_metric        → detalle por PDF
madrid_licencias        → ficha parcela
history_parsed (BOCM)   → anuncios, titular
GeoJSON capas           → mapa
```

### API propuesta (siguiente implementación)

- `GET /api/sigma/metrics/[grupo]` → fila `sigma_expediente_metric` + `hechos`
- Export estático: `web/public/data/madrid-sigma-metrics.json` en `build-data.mjs`

---

## Estados de cobertura (honestidad en UI)

| Estado | Cuándo | UI |
|--------|--------|-----|
| **Completo** | NTI + métricas + tramitación | Badge verde “Ficha enriquecida” |
| **Parcial** | Catálogo + visor, sin métricas | “Datos oficiales; análisis pendiente” |
| **Solo mapa** | Geo sin visor | “Solo ubicación en mapa” |
| **Reciente sin NTI** | ≥2020 pero sin árbol | “Expediente activo; documentos no indexados” |

---

## Fuera de alcance (v1)

- Total “viviendas que se construirán en Madrid”.
- Suma automática de viviendas por distrito sin deduplicar ámbitos.
- Garantía legal / certificación urbanística.

---

## Prioridad implementación web

1. Export `madrid-sigma-metrics.json` + KPIs en ficha y popup.
2. Bloque “Qué implica” + badges `genera_vivienda_nueva`.
3. Bloque “Fuentes” con `hechos_json`.
4. Cruce expediente ↔ parcela en `/ubicacion/[ndp]`.
5. Vista zona (lista en bbox).
