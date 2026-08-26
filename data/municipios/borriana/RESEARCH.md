# Borriana — investigación portal ayuntamiento

Municipio: **Borriana** (`borriana`) — Castellón, Comunitat Valenciana  
Boletín: DOGV (`dogv`, 2 entradas BOCM)

> **Nota:** Borriana y Burriana son el mismo municipio (ortografía valenciana vs castellana).
> El portal oficial es `burriana.es`. Implementación principal en slug `burriana` (PR #351).
> Este slug `borriana` es un alias de cola derivado del CSV DOGV.

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

1. **WordPress REST** — `?search=urbanismo&per_page=100`: noticias de PAI, unidades de ejecución (UE B-2, UE A-17…), colector, reparcelaciones, urbanizaciones.
2. **PGOU** — página estática con decenas de PDFs y ZIPs ETRS89 (`/ayuninf/PGOU/`, normas subsidiarias 2024).
3. **Tablón histórico** — directorio Apache en `/ayuninf/tablon/ORDENACION/` con subcarpetas (PUEP, plan especial casco histórico, vivienda protegida).
4. **Sede espublico** — tablón `/board` en HTML (Wicket); filas con `preview-document/{uuid}`.

## Licencias de obra

- No hay listado histórico público de concesiones.
- Trámites en sede (`/dossier`): licencias de obra, comunicaciones previas, declaraciones responsables.
- El adapter devuelve páginas informativas del tablón y catálogo de trámites.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Diputación Castellón (OpenDataSoft): `planeamiento-urbanistico`, `cod_mun=12039` → 33 polígonos GeoJSON.
  - ICV GVA WFS: `https://terramapas.icv.gva.es/0702_Planeamiento?service=WFS&typeName=Planeamiento.Zonificacion` — 2 features (normas subsidiarias, sector La Artelina).
  - Visor GVA: https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion
- **Estrategia:** cargar polígonos DipCAS + GVA; emparejar por palabras clave en título (UE, PAI, sector Artelina…).
- **Limitaciones:** sin visor municipal enlazado a expediente; geometría solo a nivel sector/zona PGOU.

## Limitaciones generales

- `burriana.es` requiere `insecure_ssl` (certificado no válido en algunos entornos CI).
- Adapter reutilizado de `municipio/adapters/burriana.py` vía subclase `BorrianaAyuntamientoAdapter`.
