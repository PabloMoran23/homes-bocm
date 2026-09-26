# Elda — investigación portal ayuntamiento

Municipio: **Elda** (`elda`) — Alicante, Comunitat Valenciana (INE `03066`, boletín DOGV).

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Web oficial | https://www.elda.es |
| Urbanismo (categoría WP) | https://www.elda.es/urbanismo-y-actividades/ |
| Hub documentos ambientales | https://www.elda.es/urbanismo-y-actividades/documentos-intervencion-ambiental-en-tramitacion/ |
| Hub fotovoltaicas | https://www.elda.es/urbanismo-y-actividades/instalaciones-fotovoltaicas/ |
| Sede EAMIC (Munitecnia) | https://eamic.elda.es:20443/web/inicioWebc.do?opcion=noreg&entidad=03066 |
| Menú trámites EAMIC | https://eamic.elda.es:20443/cargaMenuWeb.do?entidad=03066&idioma=1 |
| Transparencia urbanismo | https://eamic.elda.es:20443/web/transparencia/QXl1bnRhbWllbnRvIGRlIEVsZGFAQEAxNDAx/03066 |
| Agenda urbana (inactiva) | http://www.agendaurbanaelda.es/ |

## Cómo se listan expedientes / planeamiento

1. **WordPress Divi** — categoría `urbanismo-y-actividades` (~67 entradas en 8 páginas). Listado HTML con `entry-title`; REST API bloqueada (`401`).
2. **Transparencia EAMIC** — árbol de epígrafes desde `1401` (instrumentos de ordenación). Subcarpetas: PGOU (`1404`), sectores/PE (`1456`), unidades de actuación (`1741`), modificaciones puntuales (`1540`), etc. Documentos en JS `tbody.append` con `verDoc(idDoc)`; descarga vía `POST /web/transparencia.do` opción `6`.
3. **Hubs estáticos WP** — PDFs de intervención ambiental y instalaciones fotovoltaicas enlazados en páginas hijas.

## Licencias de obra

- La sede **EAMIC** expone catálogo de trámites vía menú JS (ventanilla virtual); no hay tablón RSS público ni listado de concesiones.
- Noticias estadísticas sobre licencias en la categoría urbanismo WP (p. ej. licencias de vivienda, actividad comercial).
- El adapter devuelve páginas informativas de la sede + noticias WP con keywords de licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** ICV Terramapas WFS `InventarioSuSuz` filtrado por `cod_ine_mun=03066` — 2 polígonos SU (UA-35, UA-63).
- **Estrategia:** paginación WFS (`STARTINDEX`) + cruce por tokens de sector/UA en títulos de transparencia/WP.
- **Limitaciones:** solo 2 unidades en inventario ICV; documentos PDF de planeamiento sin georreferencia; sede EAMIC requiere `insecure_ssl` (certificado autofirmado en `:20443`); REST WP cerrada.

```yaml
geometry_status: partial
```

## Limitaciones generales

- Sin visor ArcGIS municipal enlazado a expedientes individuales.
- Transparencia EAMIC codificada en ISO-8859-15 con epígrafes Base64 (`Ayuntamiento de Elda@@@<id>`).
- `agendaurbanaelda.es` no responde contenido útil.
- Provincia en cola CSV aparece como "Elda" pero el municipio es de la provincia de **Alicante**.
