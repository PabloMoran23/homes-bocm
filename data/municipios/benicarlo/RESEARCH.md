# Benicarló — investigación portal ayuntamiento

**Slug:** `benicarlo`  
**Provincia:** Castellón  
**Comunidad Autónoma:** Comunitat Valenciana  
**INE:** 12018  
**Boletín:** sin entrada asociada en histórico BOCM (`bocm_count: 0`)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.benicarlo.org | **Operativa** — PHP propietario (no Drupal). `www.benicarlo.es` no resuelve DNS. |
| Sede electrónica | https://benicarlo.sedipualba.es | **Operativa** — plataforma sedipualba (Diputación Albacete) |
| Tablón de anuncios | https://benicarlo.sedipualba.es/tablondeanuncios/default.aspx | **Operativa** — filtro categoría «Urbanisme» (id=427) |
| RSS tablón | https://benicarlo.sedipualba.es/tablondeanuncios/tablon_rss.aspx | **Operativa** — items `anuncio.aspx?id=` |
| Catálogo trámites | https://benicarlo.sedipualba.es/catalogoservicios.aspx | **Operativa** — licencias vía sede (sin histórico público) |
| Sede espublico | https://benicarlo.sedelectronica.es/board | **No usar** — página de selección de sede, no tablón operativo |

## Cómo se listan expedientes

- **Tablón sedipualba:** tabla HTML en `default.aspx` + feed RSS. Anuncios de planeamiento, licencias y actuaciones urbanísticas mezclados con otros anuncios municipales.
- **Filtrado en adapter:** regex urbanística sobre título RSS (licencias, PGOU, sectores, información pública, etc.) excluyendo personal/subvenciones salvo mención urbanística.
- No hay listado estructurado de expedientes de información pública aparte del tablón.

## Licencias de obra

- No existe dataset histórico descargable con coordenadas.
- Edictos de concesión/comunicación previa aparecen en el RSS del tablón cuando se publican.
- El adapter incluye dos filas informativas: enlace al tablón y catálogo de trámites de la sede (patrón Pozuelo).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor municipal gvSIG Online: `https://sig.ajuntamentdebenicarlo.org/gvsigonline/core/public_project_load/12/`
  - ICV WFS `InventarioSuSuz`: `https://terramapas.icv.gva.es/0702_Planeamiento` (escaneo paginado; el filtro CQL del servicio no aplica en servidor)
  - Visor regional: `https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz`
- **Estrategia:** visor gvSIG municipal; inventario ICV descartado en ingesta (geometrías con `cod_ine_mun=12018` caen fuera del término en validación geográfica).
- **Limitaciones:**
  - Sin enlace expediente-tabla en sedipualba.
  - ICV WFS no fiable para Benicarló (polígonos fuera de `municipality_scope`).
  - Tablón RSS sin geometría embebida.

## Adapter implementado

- `municipio.adapters.benicarlo:BenicarloAyuntamientoAdapter`
- Extiende la lógica compartida de `benicarlo_vinaros_benijofar` limitada al municipio Benicarló.
- Fuentes: RSS + tablón HTML sedipualba + semillas (gvSIG, datos abiertos GVA).
