# L'Alcúdia — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Municipio | L'Alcúdia (Valencia) |
| Web oficial | https://www.lalcudia.com/web/ |
| CMS | Joomla 2.5 / JSN Boot Pro |
| Sede electrónica | https://lalcudia.sede.gva.es — **503 Service Unavailable** |
| Sede legacy | https://lalcudia.sedipualba.es — **inactiva** (noactiva.aspx) |
| ICV cod_ine_mun | 46019 |

## URLs base y páginas semilla

| Sección | URL |
|---------|-----|
| Portada | https://www.lalcudia.com/web/ |
| PGOU / ordenación urbana | https://www.lalcudia.com/web/index.php?option=com_content&view=article&id=116 |
| Planificación (índice) | https://www.lalcudia.com/web/index.php?option=com_content&view=article&id=431 |
| Trámites urbanismo (licencias) | https://www.lalcudia.com/web/index.php?option=com_content&view=article&id=460 |
| Registro interés urbanístico | https://www.lalcudia.com/web/index.php?option=com_content&view=article&id=887 |
| PMUS | https://www.lalcudia.com/web/index.php?option=com_content&view=article&id=980 |
| Portal transparencia (índice) | https://www.lalcudia.com/web/index.php?option=com_content&view=article&id=434 |
| PDFs estáticos | https://www.lalcudia.com/ajuntament/urbanisme/… |

## Expedientes / proyectos

- **Listado:** artículos Joomla con enlaces `<a href="../ajuntament/urbanisme/...pdf">`.
- **Formato:** PDFs estáticos en `/ajuntament/urbanisme/` (PGOU, modificaciones, reparcelaciones, PAI UE07.2b, registro PAIs).
- **Sin API JSON** ni tablón de anuncios accesible (sedes caídas).
- **Instrumentos ICV:** Plan general (exp. 20000124) y PAI sector S-15 industrial (exp. 20050623).

## Licencias

- **Publicación:** solo formularios descargables (DR, LO, LO-SNU, ocupación vía pública) en artículo 460.
- **No hay** listado histórico de concesiones ni tablón operativo.
- Estrategia adapter: filas informativas de trámites (patrón Pozuelo).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Capa: `ms:Planeamiento.Zonificacion`
  - Filtro municipal: `cod_ine_mun=46019` (codificación ICV, no INE 5 dígitos)
  - Visor GVA: https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion
- **Estrategia:** `GetFeature` por `featureId` (PGOU fid 887, sector S-15 fid 889); enriquecer proyectos PDF por coincidencia de título (pgou/sector).
- **Limitaciones:**
  - Sin visor municipal propio ni geometría por expediente de licencia.
  - Sedes electrónicas inaccesibles (sin tablón enlazable).
  - PDFs de planeamiento sin georreferencia embebida; polígonos solo vía ICV para instrumentos aprobados.

## Limitaciones generales

- Sede GVA devuelve HTTP 503 (sep 2026).
- Sedipualba redirige a página inactiva.
- Joomla antiguo (2.5); menús con `javascript:void(0)`.
- Directorio `/ajuntament/` devuelve 403 en listado directo pero PDFs accesibles por URL conocida.
