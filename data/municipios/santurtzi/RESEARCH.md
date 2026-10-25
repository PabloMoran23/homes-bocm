# Santurtzi — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Portal principal | https://www.santurtzi.eus |
| Trámites (inicio) | https://www.santurtzi.eus/es-ES/Tramites/Paginas/iniciar-tramite.aspx |
| Sede / Mi ciudad | https://www.santurtzi.eus/es-ES/Mi-Ciudad/Paginas/bienvenida.aspx |
| Tablón anuncios (índice) | https://www.santurtzi.eus/es-ES/organizacion-municipal-transparencia/tablonanuncios/Paginas/default.aspx |
| Tablón — Urbanismo y Medio Ambiente | https://www.santurtzi.eus/es-ES/organizacion-municipal-transparencia/tablonanuncios/ayuntamiento/Paginas/urbanismo.aspx |
| Tablón — Obras y Servicios | https://www.santurtzi.eus/es-ES/organizacion-municipal-transparencia/tablonanuncios/ayuntamiento/Paginas/obras.aspx |
| Registro PUR Bizkaia (Santurtzi = id **82**) | https://www.bizkaia.eus/es/planeamiento-urbanistico-buscador |

CMS: **SharePoint** (rutas `Paginas/*.aspx`, listados con `<h3>` + PDF). Sede BiscayTIK integrada en el dominio municipal (trámites y notificaciones).

## Cómo se listan expedientes / proyectos

1. **Registro de Planeamiento Urbanístico (Diputación)** — Formulario Liferay `IYBIWPUC` con `select-municipios=82`. Respuesta HTML con tarjetas (año, título, enlace detalle `idInstrumento=…`). Incluye PGOU, planes parciales y modificaciones con documentación BOB.
2. **Tablón municipal** — Categorías *Urbanismo* y *Obras y Servicios*: anuncios en HTML con título (`h3`) y enlace a PDF (`_layouts/15/download.aspx` o similar). Paginación `?page=N`.

No hay visor de consulta de expediente urbanístico por código en sede pública tipo SIBAE (Barakaldo).

## Licencias de obra

- No hay dataset abierto de concesiones. El tablón puede incluir licencias / autorizaciones puntuales (p. ej. uso común especial ferias).
- Trámites de licencia de obra y urbanismo accesibles desde el portal de trámites y sede electrónica (páginas informativas; el adapter registra seeds + enlaces detectados con regex `licencia|obra`).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - `geo.bizkaia.eus` — capas metropolitanas (p. ej. `PX_Bilbao_Metropolitano_inf`) sin campo de enlace a expediente municipal ni instrumento PUR concreto.
  - Tablón y PUR — documentos PDF/HTML sin geometría embebida ni `objectId` consultable por expediente.
  - Portal municipal — sin visor urbanístico público enlazado al tablón.
- **Estrategia:** centroide municipal en manifest + jitter vía orquestador `geocode`.
- **Limitaciones:** desde algunos entornos cloud el host `www.santurtzi.eus` no completa TLS (timeout); el adapter tolera fallo del tablón y mantiene PUR Bizkaia.

## Limitaciones técnicas

- Tablón: paginación manual `?page=`; estructura SharePoint puede variar entre categorías.
- PUR Bizkaia: requiere POST con `formDate` dinámico; parseo de tarjetas HTML (no API JSON pública documentada).
- `santurtzi.eus` puede bloquear o ralentizar IPs de datacenter — ejecutar pipeline desde red residencial/CI si el tablón queda vacío.
