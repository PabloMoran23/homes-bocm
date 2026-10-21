# Cartagena — investigación portal ayuntamiento

**Municipio:** Cartagena (Murcia, Región de Murcia)  
**Slug:** `cartagena`  
**Boletín:** sin asociación en cola (`bocm_count: 0`)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web oficial | https://www.cartagena.es | Operativa — ASP.NET / IIS |
| Portal urbanismo (SIU) | https://urbanismo.cartagena.es/urbanismo/INICIO | Operativa — listas y fichas |
| Información pública | https://urbanismo.cartagena.es/urbanismo/Lista/IP | Tabla `GV_Lista` (~7 IP activas) |
| Planes urbanísticos | https://urbanismo.cartagena.es/urbanismo/Lista/PL | ~126 filas (PGMO + PAU…) |
| Estudios de detalle | https://urbanismo.cartagena.es/urbanismo/Lista/ED | ~276 filas |
| Unidades de actuación | https://urbanismo.cartagena.es/urbanismo/Lista/UA | ~618 filas |
| Convenios | https://urbanismo.cartagena.es/urbanismo/Lista/Convenio | Listado HTML |
| Sede Sedipualba | https://cartagena.sedipualba.es | Operativa |
| Tablón edictos | https://cartagena.sedipualba.es/tablondeanuncios/ | Operativa |
| Tablón RSS | https://cartagena.sedipualba.es/tablondeanuncios/tablon_rss.aspx | Feed RSS |
| Trámites urbanismo | https://cartagena.sedipualba.es/catalogoservicios.aspx?area=980 | Licencias DRUB/DRPO/CPRO… |
| GeoPortal IDE | https://ide.cartagena.es/gp_urbanismo | WMS/WFS Intergraph (planeamiento) |

## Cómo se listan expedientes

| Tipo | Mecanismo |
|------|-----------|
| Planeamiento / IP | HTML tablas `GV_Lista` en urbanismo.cartagena.es; enlace ficha `Ficha/{IP,PL,ED,UA}?Entidad=…&Valor=…&Matricula=…` |
| Mapa por instrumento | JavaScript `GeoVisor` con `CQEntidad`, `CQValor`, `CQBox` (bbox UTM EPSG:25830) |
| Tablón | Sedipualba RSS — mezcla plenos/juntas y algún edicto urbanístico |
| BORM | Grupo `Grupos/BORM` en portal urbanismo (no scrapeado en v1) |

Encoding habitual: `latin-1` / ISO-8859-1 en páginas urbanismo.

## Cómo se publican licencias

- Catálogo Sedipualba área **Urbanismo y Actividades** (id área 980): trámites 2.1.01 Licencia Urbanística, DRUB, CPRO, demolición, etc.
- Sin dataset histórico público de concesiones con dirección/coords.
- Tablón: edictos puntuales (p. ej. «ANUNCIO EXPOSICIÓN AL PÚBLICO»).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GeoVisor temático: `urbanismo.cartagena.es/urbanismo/GeoVisor?…&CQBox=xmin-ymin-xmax-ymax` (UTM 30N)
  - WMS públicos IDE: `https://ide.cartagena.es/WMS_RPG0/wmservice.aspx` (EPSG:25830)
  - GeoPortal: https://ide.cartagena.es/gp_urbanismo
- **Estrategia:** parsear `CQBox` del listado PL/ED/UA → polígono bbox en WGS84 (`pyproj` 25830→4326); centroides en adapter.
- **Limitaciones:**
  - Geometría es **bbox** del visor, no contorno parcelario exacto.
  - Filas IP sin enlace mapa.
  - Licencias sin capa GIS enlazable al expediente.
  - WMS internos (`172.19.4.235`) no accesibles desde internet.

## Limitaciones generales

- Portal urbanismo con menús ASP.NET; sin API JSON pública de expedientes.
- Tablón RSS con mucho ruido administrativo (plenos, empleo).
- Sin boletín regional asociado en pipeline BOCM para este municipio en cola.
