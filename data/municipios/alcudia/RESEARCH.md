# Alcúdia — investigación portal ayuntamiento

Municipio: **Alcúdia** (`alcudia`) — Illes Balears, Mallorca. INE **07003**. Sin boletín asociado en cola.

## URLs base

| Recurso | URL |
|---------|-----|
| Web municipal (OpenCms / Tresdigits) | https://alcudia.net |
| Ajuntament (portada) | https://alcudia.net/ajuntament/ca |
| Urbanisme (subweb) | https://alcudia.net/Urbanisme/ca |
| Tràmits urbanisme | https://alcudia.net/Urbanisme/ca/tramits/ |
| Planejament vigent | https://alcudia.net/Urbanisme/ca/planejament-vigent/ |
| Transparència urbanisme | https://alcudia.net/Urbanisme/ca/transparencia/ |
| Documents d'interès | https://alcudia.net/Urbanisme/ca/documentosDeInteres/ |
| Sede electrónica (espublico / eadministracio) | https://alcudia.eadministracio.cat |
| Tablón (espublico) | https://alcudia.eadministracio.cat/board |
| Trámites / info sede | https://alcudia.eadministracio.cat/info.0 |
| Cita previa urbanisme | https://alcudia.eadministracio.cat/citaprevia.1 |
| Visor Citymap (Tecnogeo) | https://citymap.tecnogeows.com/user/101103780093126100707/map/JvJZqsG2tuzekkreZq9d6X?tree=stage |
| SAC ABS-Atlas (normativa PDF) | http://sac.alcudia.net/ABSATLAS/NORMATIVA/PUBLICACION_WEB/PORTADA-2.PDF |
| SITMUN IDELMA | https://sitmun.idelma.cat/urb_alcudia |
| Visor IDE M003 | https://ide.idelma.cat/visormap/Visors/ide/html/visor003.html |

**Nota DNS:** `www.alcudia.es` / `alcudia.sedelectronica.es` resuelven a `185.128.8.3` pero suelen **bloquear o time-out** desde IP de datacenter; la web operativa accesible es **alcudia.net**.

## Cómo se listan expedientes / planeamiento

### Web OpenCms (`alcudia.net/Urbanisme`)

HTML estático por subweb. **Planejament vigent** enlaza:

- Portada normativa SAC (`sac.alcudia.net/ABSATLAS/...`)
- Fichas PDF de **modificaciones** (`MODI_12`, `MODI_16`, `AN6/...`)
- Planols NNSS (`sac.alcudia.net/absatlas/Normativa/NNUU_PLANOLS%20NNSS/*.pdf`)
- PDF local MP2-NNSS (`/export/sites/default/Urbanisme/...`)

No hay API JSON ni listado estructurado de expedientes en información pública; el adapter hace crawl de semillas + extracción de PDFs urbanísticos.

### Tablón sede (eadministracio.cat)

Mismo patrón espublico que Manacor/Pollença: filas `<tr><td class="class_name">` en `/board`. Desde red del agente: **timeout** frecuente (misma infra que sede bloqueada).

### Visor Citymap (Tecnogeo)

SPA con `search.tecnogeows.com`; mapa parcelario/urbanístico municipal. Sin WFS público documentado en el HTML de arranque; consulta por parcela en UI.

### SAC ABS-Atlas

Repositorio HTTP de normativa y modificaciones (PDF). `sac.alcudia.net` a veces **lento o inaccesible** desde datacenter.

## Licencias de obra

No hay dataset abierto de licencias concedidas. Fuentes:

1. Texto legal en `/Urbanisme/ca/tramits/` (competencias: llicències, comunicacions prèvies, declaracions responsables).
2. Sede `info.0` y `citaprevia.1` (trámites informativos).
3. **WFS IDELMA `exp_absis`** — expedientes históricos Absis con descripción de obra/licencia (si el GeoServer responde).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer IDELMA `M003_URBANISME:exp_absis` (patrón INE 07003 → M003, análogo a Pollença M042)
  - Visor Citymap TecnoGeo (parcelas; sin query masiva por expediente)
  - SAC / PDFs sin georreferencia embebida
- **Estrategia:** `GetFeature` WFS con `outputFormat=application/json&srsName=EPSG:4326`; centroide del polígono → `lat`/`lon`
- **Limitaciones:**
  - IDE IDELMA / `sitmun.idelma.cat`: fallo TLS (`SSL EOF`) desde el entorno del agente (puede funcionar en red residencial/CI con otra IP)
  - Sede y `alcudia.es` bloqueados por timeout en datacenter
  - Citymap sin API WFS pública alineada con códigos de expediente
  - PDFs dominan el planeamiento publicado

## Limitaciones generales

- Dominio oficial `.es` poco accesible; producción usa **alcudia.net**.
- OpenCms sin RSS urbanismo.
- `sac.alcudia.net` HTTP mezclado con HTTPS en enlaces.
- Sin re-parse BOCM (municipio sin `boletin_source_id` en cola).
