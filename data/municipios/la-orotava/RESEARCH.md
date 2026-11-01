# La Orotava — investigación portal ayuntamiento

## URLs base y semillas

| Fuente | URL |
|--------|-----|
| Web municipal (Drupal 10) | http://www.laorotava.es |
| Urbanismo | http://www.laorotava.es/es/areas-municipales/area-de-urbanismo-y-ordenacion-del-territorio |
| Planeamiento en información pública | http://www.laorotava.es/es/areas-municipales/planeamiento-en-informacion-publica |
| Planes parciales / especiales | `/es/areas-municipales/planes-parciales`, `/es/areas-municipales/planes-especiales` |
| Instancias descargables | http://www.laorotava.es/es/tramites/descarga-instancias |
| Sede electrónica (espublico) | https://laorotava.sedelectronica.es |
| Tablón de anuncios | https://laorotava.sedelectronica.es/board |
| SITCAN CKAN | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-la-orotava |
| GEOBDP municipio (INE 38026) | https://geobdp.grafcan.es/core/municipios/38026/ |

## Proyectos / expedientes

- **Listado principal:** página Drupal *Planeamiento en Información Pública* con bloques por actuación (convenios, modificaciones, sectores) y enlaces a PDFs en `/sites/default/files/` y BOP/BOC.
- **Histórico sistematizado:** API CKAN `package_show` del dataset SITCAN (48 recursos SIPU/PDF/HTML GEOBDP).
- **Sede:** tablón `/board` (HTML tabla espublico); consulta de expedientes en `/expedientes` requiere identificación electrónica (certificado, DNIe, Cl@ve).

## Licencias de obra

- No hay dataset público de licencias concedidas con coordenadas.
- Trámites: sede (catálogo), descarga de instancias en la web, y tablón para edictos/notificaciones (cuando publican licencias u obras).
- El adapter incluye filas informativas de trámites (patrón Pozuelo/Güímar) y licencias detectadas en tablón/PDFs.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP Grafcan: cada instrumento SIPU enlaza a `geobdp.grafcan.es/core/documentos/{id}.html` con `App.Map.zoomToExtent` (GeoJSON en UTM28N → reproyección WGS84 en el adapter).
  - IDECanarias WMS planeamiento vigente: `https://idecan2.grafcan.es/ServicioWMS/Planeamiento?` (capas municipales, sin join por expediente concreto).
  - Visor general: https://visor.grafcan.es/
- **Estrategia:** emparejar títulos SITCAN/portal con índice GEOBDP del municipio 38026 y extraer polígono del visor documental.
- **Limitaciones:** licencias sin GIS; expedientes sede cerrados; geometría solo a nivel de instrumento de planeamiento (no parcela de licencia individual).

## Limitaciones técnicas

- Certificado TLS de `laorotava.sedelectronica.es` inválido en algunos entornos → `insecure_ssl: true` en manifest.
- Planeamiento web mezcla HTML manual + PDFs; fechas inferidas de nombre de archivo o texto.
- Sin API JSON de expedientes urbanísticos en portal abierto.
