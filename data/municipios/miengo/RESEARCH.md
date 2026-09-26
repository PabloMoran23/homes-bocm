# Miengo — investigación portal ayuntamiento

**Municipio:** Miengo (Cantabria)  
**Fecha:** 2026-09-23

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal (WordPress Avada) | https://www.aytomiengo.org | Portal activo (`www.miengo.es` no resuelve) |
| Tablón de anuncios | https://www.aytomiengo.org/tablon-de-anuncios/ | **Fuente principal** — bloques `<h3>` + PDFs (licencias, IP, plan parcial El Somo) |
| Urbanismo / PGOU | https://www.aytomiengo.org/urbanismo/ | PGOU 2015, callejero y planos PDF |
| PGOU PDFs | https://www.aytomiengo.org/data/pgou/ | Memoria, ordenanzas, planos hoja 01–11 |
| Sede electrónica | https://sedemiengo.simplificacloud.com/ | Absis eAtiende/eConstruye (trámites; sin listado público de concesiones) |
| AUCAN (Gob. Cantabria) | https://aplicacionesweb.cantabria.es/aucan/public/zona/costacentral/miengo | Archivo regional planeamiento |
| Transparencia | https://transparencia.aytomiengo.org | Portal Bootstrap (valor limitado para urbanismo) |
| BOC Cantabria | https://boc.cantabria.es | Enlaces desde tablón (`boletin_source_id: boc_cantabria`) |

## Cómo se listan expedientes

- **Tablón WordPress:** página única con ~40 anuncios en `<h3>` + fecha `publicado el DD de Mes de YYYY` + enlaces PDF (`/wp-content/uploads/` y `/data/tablon-anuncios/`).
- **Expedientes identificables:** regex `EXPEDIENTE NNN/YY` en títulos (p. ej. 366/23, 149/25, 383/23).
- **Urbanismo:** página estática con PDFs PGOU 2015; no hay listado dinámico de expedientes.
- **REST API WP:** habilitada pero el tablón **no** está modelado como posts individuales.
- **AUCAN:** documentación histórica de planeamiento (complemento, no sustituto del tablón).

## Cómo se publican licencias

- **Tablón:** concesiones de primera ocupación, solicitudes IP de licencia de actividad, autorizaciones en suelo rústico (con dirección y nº expediente).
- **Sede Absis:** catálogo de trámites genéricos; no expone listado histórico scrapeable.
- **Sin dataset abierto** de licencias georreferenciadas.
- Estrategia adapter: tablón + páginas informativas (urbanismo, sede).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - SIUCAN WFS Cantabria: `https://geoservicios.cantabria.es/inspire/services/Urbanismo/MapServer/WFSServer`
  - Capa: `Urbanismo:Sectores`
  - Filtro client-side: `Código_INE = 39044` / `Denominación_Municipio = Miengo` (CQL server-side no fiable)
  - 13 sectores con polígono (p. ej. `B. UA-2` El Somo, `S5` Residencial Miengo, `S1` Gornazo)
  - Visor regional: https://mapas.cantabria.es/
- **Estrategia:** ingestar sectores WFS como proyectos con `geom_geojson`; enriquecer filas del tablón por código de sector en título (`B-UA.2`, `Sector 5`, `El Somo`, …).
- **Limitaciones:**
  - Sin visor municipal enlazado a expedientes individuales.
  - Licencias del tablón solo tienen dirección textual (sin polígono).
  - WFS no soporta `outputFormat=application/json`; se parsea GML3.
  - MapServer REST query devuelve 403 desde CI.

## Limitaciones generales

- Municipio costero cantábrico (~5.600 hab.); volumen moderado en tablón.
- Anuncios administrativos (oposiciones, becas) mezclados — filtrados por regex.
- Sede Absis distinta del patrón espublico gestiona (`/board/`).
- SSL válido en web principal.
