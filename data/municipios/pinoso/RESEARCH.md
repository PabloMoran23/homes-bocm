# Pinoso — investigación portal ayuntamiento

**Municipio:** Pinoso / El Pinós (Alicante, Comunitat Valenciana)  
**Slug:** `pinoso`  
**INE:** 03095  
**Boletín:** DOGV (`dogv`, 2 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web oficial | https://www.pinoso.es | Operativa — WordPress (Kadence) |
| Urbanismo (concejalía) | https://www.pinoso.es/el-ayuntamiento/concejalias/concejalia-mantenimiento-y-orden-urbano/ | Operativa — enlaces trámites y sede |
| Trámites y gestiones | https://www.pinoso.es/el-ayuntamiento/tramites-y-gestiones/ | Operativa — PDFs licencias obra/actividad |
| Sede Sedipualba | https://pinoso.sedipualba.es | **Operativa** — plataforma ASP.NET Sedipualba |
| Tablón de anuncios | https://pinoso.sedipualba.es/tablondeanuncios/ | Operativa |
| Tablón RSS | https://pinoso.sedipualba.es/tablondeanuncios/tablon_rss.aspx | Feed RSS determinista (~6 items ago 2026) |
| Catálogo trámites | https://pinoso.sedipualba.es/catalogoservicios.aspx | Operativa — trámites genéricos |
| Sede eAdmin | https://sede.pinoso.es | Operativa — registro/carpeta ciudadano |
| Sede espublico | https://pinoso.sedelectronica.es | **No operativa** — «Sede Electrónica Indeterminada» |
| Sede histórica | https://www.pinoso.es/sede_electronica_2016-2024/ | Redirige a Sedipualba |

## Cómo se listan expedientes

| Tipo | Mecanismo |
|------|-----------|
| Planeamiento aprobado | ICV WFS InventarioSuSuz (19 sectores SU/SUZ) + Zonificacion (68 polígonos) |
| Noticias urbanísticas | WordPress — búsqueda `?s=urbanismo`, `estudio de detalle`, etc. |
| Tablón | Sedipualba RSS — mayormente personal/tributos (ago 2026) |
| Transparencia | Sin portal transparencia urbanismo dedicado en sede activa |

### Noticias WP relevantes (2023–2025)

- Aprobación estudio de detalle Área de Reparto EA-8
- Ampliación Polígono Industrial
- IATE para planificación estratégica

## Cómo se publican licencias

- Impresos descargables en web municipal (obra menor, actividad, obras mayores)
- Sin dataset histórico de concesiones con coordenadas
- Tablón Sedipualba sin licencias urbanísticas recientes en RSS
- Trámites presenciales / sede eAdmin (sin listado público de expedientes)

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `terramapas.icv.gva.es/0702_Planeamiento`
  - `InventarioSuSuz` — 19 instrumentos (S1–S11 Saladar-Tossals, Marjals, UA1–UA5, etc.)
  - `Planeamiento.Zonificacion` — PGOU y modificaciones (exp. 20080547 Marjals, 20021495 SNU arqueológica)
  - Filtro cliente: `cod_ine_mun=03095` (CQL_FILTER del servidor no fiable)
- **Estrategia:** paginación WFS GML3 (`STARTINDEX`); matching título↔sector (EA-8, Marjals, Tossals…)
- **Limitaciones:**
  - Geometría ICV es zonificación/sectores aprobados, no parcela ni licencia individual
  - Escaneo InventarioSuSuz completo ~3 min (paginación 200 en ~80 páginas)
  - Tablón RSS sin anuncios urbanísticos recientes
  - `pinoso.sedelectronica.es` inactivo; sin visor municipal ArcGIS identificado

### Instrumentos ICV InventarioSuSuz (cod_ine_mun=03095)

| Sector | Clasificación |
|--------|---------------|
| S1–S4 Saladar-Tossals | SUZ |
| S5, S6, S7 Marjals | SUZ |
| PP1 Partida Tossals, PP2 Partida Marjals | SUZ |
| UA1–UA5, UE Tossals-2, UE Patins-Urbà/2006 | SU/SUZ |

## Limitaciones generales

- Sede espublico histórica no resuelve al ayuntamiento
- WP REST API deshabilitada; crawl HTML vía búsqueda
- Tablón con pocos anuncios y sin urbanismo en feed actual
- Provincia en `queue.yaml` incorrecta (`Pinoso-Alicante`); manifest usa `Alicante`

## Adapter implementado

- `municipio.adapters.pinoso:PinosoAyuntamientoAdapter`
- Fuentes: tablón RSS Sedipualba + ICV WFS (SUZ+Zon) + noticias WP + impresos trámites
- IDs: `pinoso-lic-*` / `pinoso-proy-*` (sha256[:14])
