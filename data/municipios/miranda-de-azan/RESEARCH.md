# Investigación portal — Miranda de Azán

Municipio: **Miranda de Azán** (`miranda-de-azan`) — Salamanca, Castilla y León.  
Boletín: **BOCyL** (`bocyl`), 4 entradas históricas.

## URLs base y páginas semilla

| Fuente | URL | Notas |
|--------|-----|-------|
| Web municipal | https://www.mirandadeazan.com | Jimdo Creator |
| Área urbanismo | https://www.mirandadeazan.com/areas/urbanismo/ | Hub con enlaces a subsecciones |
| Normas urbanísticas (NS) | https://www.mirandadeazan.com/areas/urbanismo/normas-urbanísticas/ | ~30 PDFs plan vigente + modificaciones Los Guijos |
| Modificación puntual NS | https://www.mirandadeazan.com/areas/urbanismo/autorizaciones-de-uso/ | PDFs `I_MA_*`, `MA_PLANOS` (memoria modificación) |
| Plan especial Las Liebres | https://www.mirandadeazan.com/areas/urbanismo/planes-especiales/ | PEOD + proyecto actuación + urbanización |
| Estatutos urbanización | https://www.mirandadeazan.com/areas/urbanismo/estatutos-urb-las-liebres/ | PDF estatutos |
| Autorizaciones / licencias | https://www.mirandadeazan.com/areas/urbanismo/autorizaciones-de-uso/ | Edictos uso, licencia 1ª ocupación, proyectos obra |
| Edictos ayuntamiento | https://www.mirandadeazan.com/tu-ayuntamiento/edictos/ | Mayoría no urbanísticos |
| Sede electrónica | https://mirandadeazan.sedelectronica.es | espublico gestiona — **certificado SSL inválido** |
| Tablón sede | https://mirandadeazan.sedelectronica.es/board | Vacío (sin filas preview-document) |
| Trámites sede | https://mirandadeazan.sedelectronica.es/dossier | Catálogo trámites (lento; fallback informativo) |
| Diputación Salamanca | http://www.lasalina.es/...codMunicipio=192 | Ficha municipal; planeamiento = **NS** |

## Formato de datos

### Web Jimdo
- CMS **Jimdo Creator**; documentos en `href="/app/download/{id}/{nombre}.pdf?t=..."`.
- Sin API JSON; scrape HTML determinista de páginas semilla.
- Descarga absoluta: `https://www.mirandadeazan.com/app/download/...`

### Sede espublico
- Tablón HTML con tabla `preview-document` (patrón Pelabravo/Ciudad Rodrigo).
- Tablón actualmente **sin anuncios** publicados.
- SSL: certificado no confiable en CI → `insecure_ssl: true`.

### Licencias
- Publicadas como PDFs en «Autorizaciones de Uso»: edicto autorización uso SUNC, licencia 1ª ocupación, final de obra, ampliación vivienda, proyectos CTE (cobertizo, piscina).
- No hay listado tabular de concesiones con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capa `urbanismo:plau_cyl_instrumentos_ambito` — 1 polígono NUM «NORMAS URBANÍSTICAS MUNICIPALES» (~24 km²)
  - Capa `urbanismo:plau_cyl_sectores` — 4 sectores con MultiPolygon:
    - I1 (`37192I1`)
    - R1 (`37192R1`)
    - Los Guijos / SUNC-R1 (`37192SUNC-R1`)
    - Las Liebres R2 (`37192R2`)
- **Estrategia:** query WFS por `n_mun = 'Miranda de Azán'`; enriquecer filas portal por tokens en título (`liebres`, `guijos`, `I1`, `R1`, `normas`/`NUM` → instrumento municipal).
- **Limitaciones:** PDFs de licencias individuales sin georef; tablón vacío; no hay visor ArcGIS municipal propio. Diputación indica NS sin PGOU aprobado.

## Limitaciones

- Sede con certificado SSL defectuoso (requiere `insecure_ssl`).
- Tablón de anuncios vacío — proyectos recientes solo en web Jimdo si el ayto los sube manualmente.
- `/dossier` responde lento (>20 s); adapter incluye catálogo con timeout generoso.
- Muchos PDFs son volúmenes del mismo instrumento (NS / PEOD); adapter emite una fila por documento.

## Adapter

`municipio/adapters/miranda_de_azan.py` — Jimdo PDFs + sede tablón/catálogo + IDECyL WFS geometría.
