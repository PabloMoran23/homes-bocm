# Maó — investigación portal ayuntamiento

Municipio: **Maó** (`mao`) — Illes Balears, Menorca. INE 07032. Sin boletín regional asociado en cola.

## URLs base

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.ajmao.org |
| Área Urbanisme | https://www.ajmao.org/Publicacions/Area.aspx?ID=29 |
| Tauler d'edictes (exposición pública) | https://www.ajmao.org/tauler/edictesx.aspx?tipo=01 |
| Histórico tablón | https://www.ajmao.org/tauler/edictesx.aspx?tipo=01&HISTORIC=1 |
| Detalle edicto | https://www.ajmao.org/Tauler/ObrirEdicte.aspx?Id={id} |
| PGOU 2012 (documentos) | https://www.ajmao.org/Contingut.aspx?IdPub=12029 |
| Normativa en trámite | https://www.ajmao.org/contingut.aspx?IdPub=33367 |
| Consulta pública previa | https://www.ajmao.org/contingut.aspx?IdPub=33371 |
| Seu / Carpeta ciutadana | https://www.carpetaciutadana.org/mao/Portal.aspx |
| Trámites gesserveis (obras, certificados) | https://www.ajmao.org/gesserveis/gestion.aspx?idgestion=58 |
| Transparencia | https://governobert.ajmao.org/ |
| Visor IDE Menorca | https://ide.cime.es/visor/ |
| Cartografia CIME | https://cartografia.cime.es/ |

## Cómo se listan expedientes

### Tablón de edictes (`edictesx.aspx`)

Grid DevExpress (`dxeHyperlink_Moderno`). Columnas: título (enlace a `ObrirEdicte.aspx?Id=` o PDF en `bpm.ajmao.org`), fechas de publicación y plazo ciudadano (DD/MM/YYYY).

Expedientes urbanísticos incluyen código en título (`EXP. ED01-2020-000003`, `EXP. U005-2026-000001`, `EXP. UR028-2026-000001`). Algunos anuncios citan **referencia catastral** (p. ej. `7668811FE0176N0001UQ`).

La vista histórica (`HISTORIC=1`) repite el mismo patrón; no hay RSS ni API JSON pública.

### Consulta de expedientes

Solo **carpeta ciutadana** con PIN o certificado (registro entradas/salidas). No scrapeable sin credenciales.

### Planeamiento documental

PGOU 2012 y normativa en páginas CMS con enlaces PDF bajo `/WebEditor/Pagines/File/Urbanisme/`. No hay listado estructurado de expedientes abiertos aparte del tablón.

## Licencias de obra

No hay dataset abierto de licencias concesionadas (como Madrid). Fuentes:

1. **Tablón** — edictos puntuales (p. ej. suspensión licencias piscinas `UR028-2026-000001`).
2. **gesserveis** — fichas informativas de trámites (licencia con proyecto, certificado urbanístico).
3. **Carpeta ciutadana** — consulta autenticada.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDE Menorca `urbanisme:or032pgo_solurba_su` — ámbitos de suelo urbano PGOU Maó (polígonos, campo `nom`)
  - WFS `base_referencia:ca007ins_parcela` — parcelas catastrales Menorca (`nationalcadastralreference`, `idmun=07032`)
  - Visor https://ide.cime.es/visor/ con capa WMS `urbanisme/wms` (UR032PGOU_solurba)
- **Estrategia:**
  - Si el edicto incluye referencia catastral → query WFS parcela (14 primeros caracteres de la ref.)
  - Si el título menciona nombre de ámbito PGOU (`nom` en solurba) → polígono del ámbito
  - Filas PGOU WFS como proyectos de referencia con geometría
- **Limitaciones:**
  - Sin capa WFS de expedientes/licencias enlazada por código `EXP.*` (a diferencia de Pollença/Absis)
  - Tablón sin coordenadas embebidas
  - Muchos edictos son contratación/subvenciones (sin geometría)
  - Consulta expediente requiere autenticación

## Limitaciones generales

- CMS propio ajmao.org; tablón mezcla urbanismo con otras materias.
- Descargas BPM en dominio `bpm.ajmao.org`.
- Email urbanismo: urbanismo@ajmao.org
