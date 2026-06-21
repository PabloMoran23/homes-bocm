# Colmenar Viejo — investigación portal ayuntamiento

## Resumen

Sede electrónica propia en `https://carpeta.colmenarviejo.es/eAdmin` (Java/JSP, plataforma
eAdmin). El **tablón digital de anuncios y edictos** es la fuente scrapeable principal para
licencias y expedientes de urbanismo.

La web municipal (`colmenarviejo.com`) devuelve **403 Forbidden** desde IPs automatizadas
(incluso con User-Agent de navegador y Referer de la sede). No se usa en la ingesta.

El portal de transparencia (`transparencia.colmenarviejo.es`) redirige a
`gobiernoabierto.colmenarviejo.com` (timeout desde entorno CI); no es necesario para paridad.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Tablón edictos (vigentes) | `/eAdmin/Tablon.do?action=verAnuncios` | HTML tabla | Edictos IP, aprobaciones urbanísticas, L.A. |
| Búsqueda tablón | POST `Tablon.do?action=verAnuncios` + `referenciaBusqueda` | HTML tabla | Filtrado por palabra clave |
| Detalle anuncio | `/eAdmin/Tablon.do?action=verAnuncio&id={hex}` | HTML | Fechas publicación, identificador expediente |
| PDF documento | `/eAdmin/ValidarDocumento.do?id_Documento={token}&tipo=doc&mode=ori` | PDF (redirect) | Documento original del edicto |
| Catálogo trámites urbanismo | `/eAdmin/Registrar.do?action=listadoEntradas` (filtro Urbanismo) | HTML modales | Trámites licencia/DR (informativos) |

## Estructura HTML tablón

Tabla `#table1` con filas `<tr>` de tres columnas:

1. Iconos: `abrirOriginal('{token}')` (PDF) y `verAnuncio&id={id}` (detalle)
2. Título: p. ej. `TB URBANISMO EXP. 17838/2025 APROBACION DEFINITIVA PROYECTO DE ENLACE M-607`
3. Periodo: `Periodo: DD/MM/YYYY - DD/MM/YYYY`

Token PDF → URL vía `funciones.js`:

```javascript
function abrirOriginal(codigo) {
  window.open("./ValidarDocumento.do?id_Documento="+codigo+"&tipo=doc&mode=ori", ...);
}
```

## Licencias

No hay listado tabular de concesiones con coordenadas (sin paridad Madrid capital).

Las licencias proceden de:

- Edictos del tablón con `L.A.`, `LICENCIA`, `ACTIVIDADES` en el título
- Páginas informativas de trámites urbanismo en el catálogo de la sede (tipoReg 59–64, 93–96, 127–128, 152–153)

## Proyectos / expedientes

Filas del tablón que mencionan urbanismo, información pública, PFOT, aprobación, expropiación,
plan, PGOU, convenio, etc.

Ejemplos vigentes (jun 2026):

- `TB URBANISMO EXP. 17838/2025` — aprobación definitiva enlace M-607
- `TB PFOT-754 ANUNCIO INFORMACION PUBLICA INSTALACION "GR BISBITA..."`

## Limitaciones

- `colmenarviejo.com` bloqueado (403) — no accesible a PGOU/impresos web
- Tablón muestra anuncios **vigentes**; histórico requiere búsqueda por términos
- PDFs vía token codificado; URL estable usando token como clave
- Sin geolocalización (`lat`/`lon` = null)
- `gobiernoabierto.colmenarviejo.com` inaccesible desde CI (timeout)

## Referencia adapters

- Estilo tablón + regex: `mostoles.py`, `getafe.py`
- Trámites informativos licencia: `pozuelo.py`, `fuenlabrada.py`
