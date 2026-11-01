# Puig de Santa Maria — investigación portal ayuntamiento

**Municipio:** Puig de Santa Maria (El Puig de Santa Maria, Valencia, Comunitat Valenciana)  
**Slug:** `puig-de-santa-maria` (alias BOletín DOGV; portal idéntico a `el-puig-de-santa-maria`)  
**INE:** 46104  
**Boletín:** DOGV (`dogv`)

> Investigación detallada en `data/municipios/el-puig-de-santa-maria/RESEARCH.md`. Este slug duplica el mismo ayuntamiento con otra entrada en la cola histórica.

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web oficial | https://www.elpuig.es | Drupal 10 (Digital Value); a veces lento en CI |
| Sede electrónica | https://elpuig.sede.dival.es | **Operativa** — Dival/Sedipualba |
| Tablón RSS | https://elpuig.sede.dival.es/tablondeanuncios/tablon_rss.aspx | Feed determinista |
| Urbanismo (catálogo) | https://elpuig.sede.dival.es/catalogoservicios.aspx?area=1835&ambito=1 | Trámites URB01–URB21 |

## Listado expedientes / licencias

- **Tablón:** RSS + `anuncio.aspx` / PDF `documento.aspx`.
- **Licencias:** sin dataset de concesiones; edictos en tablón + trámites informativos URB* en sede.
- **Planeamiento:** edictos DOGV/tablon (modificación puntual Plansmar, TAG urbanismo, etc.).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** ICV GVA WFS `terramapas.icv.gva.es/0702_Planeamiento`, capa `Planeamiento.Zonificacion`, `cod_ine_mun=46104`.
- **Estrategia:** paginación WFS por `startIndex`; merge polígonos por keywords (PGOU, normas subsidiarias, PRI, ordenanza).
- **Limitaciones:** sin geometría por expediente del tablón; solo instrumentos de planeamiento en WFS.

## Adapter

- `municipio.adapters.puig_de_santa_maria:PuigDeSantaMariaAyuntamientoAdapter` (hereda lógica Dival + ICV).
- IDs: `puig-de-santa-maria-lic-*` / `puig-de-santa-maria-proy-*`.
