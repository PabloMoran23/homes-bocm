# Burriana — investigación portal ayuntamiento

Municipio: **Burriana** (`burriana`) — Castellón, Comunitat Valenciana  
Boletín: DOGV (`dogv`, 3 entradas BOCM)

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web corporativa | https://burriana.es |
| Urbanismo (servicios) | https://burriana.es/servicios-municipales/urbanismo/ |
| PGOU / normativa | https://burriana.es/ayuntamiento/normativa/plan-general-de-ordenacion-urbana/ |
| Tablón ordenación (histórico) | https://burriana.es/ayuninf/tablon/ORDENACION/ |
| Sede electrónica (espublico) | https://burriana.sedelectronica.es |
| Tablón de anuncios | https://burriana.sedelectronica.es/board |
| Catálogo trámites | https://burriana.sedelectronica.es/dossier |
| WordPress REST | https://burriana.es/wp-json/wp/v2/posts |

## Cómo se listan expedientes / proyectos

1. **WordPress REST** — `?search=urbanismo&per_page=100`: noticias de PAI, unidades de ejecución (UE B-2, UE A-17…), colector, reparcelaciones, urbanizaciones. REST habilitado; categoría `Urbanismo` (id 153) sin entradas directas.
2. **PGOU** — página estática con decenas de PDFs y ZIPs ETRS89 (`/ayuninf/PGOU/`, `/wp-content/uploads/2025/01/TextoRefundidoNormasUrbanisticas-Diciembre2024.pdf`).
3. **Tablón histórico** — directorio Apache en `/ayuninf/tablon/ORDENACION/` con subcarpetas (PUEP, plan especial casco histórico, vivienda protegida, evaluación ambiental PGOU).
4. **Sede espublico** — tablón `/board` en HTML (Wicket); filas con `preview-document/{uuid}`. En la muestra actual predominan anuncios administrativos (modificación créditos, notaría); sin filas urbanísticas activas en el momento de la investigación.

## Licencias de obra

- No hay listado histórico público de concesiones.
- Trámites en sede (`/dossier`): licencias de obra, comunicaciones previas, declaraciones responsables (catálogo espublico).
- El adapter devuelve páginas informativas del tablón y catálogo de trámites (patrón Pozuelo/Coín).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Diputación Castellón (OpenDataSoft): `planeamiento-urbanistico`, `cod_mun=12039` → 33 polígonos GeoJSON (normas subsidiarias / calificación suelo EIEL 2021).
  - ICV GVA WFS: `https://terramapas.icv.gva.es/0702_Planeamiento?service=WFS&typeName=Planeamiento.Zonificacion` — 2 features Burriana (normas subsidiarias, sector La Artelina).
  - Visor GVA: https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion
  - PGOU municipal: shapefiles ZIP (`PG1000_ETRS89.zip`, etc.) en `/ayuninf/PGOU/` — no queryables por expediente.
- **Estrategia:** cargar polígonos DipCAS + GVA; emparejar por palabras clave en título (UE, PAI, sector Artelina, Cañada Blanch, normas subsidiarias…).
- **Limitaciones:** sin visor municipal enlazado a expediente; tablón sede sin coords; geometría solo a nivel sector/zona PGOU, no por licencia individual.

## Limitaciones generales

- `burriana.es` requiere `insecure_ssl` (certificado no válido en algunos entornos CI).
- Tablón sede paginado (~10 filas visibles); sin API JSON.
- DipCAS y GVA WFS son lentos (30–90 s la primera carga WFS).
- Sin re-parse BOCM/DOGV; proyectos del boletín ya en `projects.json`.
