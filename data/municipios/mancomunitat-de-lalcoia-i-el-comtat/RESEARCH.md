# Mancomunitat de L'Alcoià i El Comtat — investigación portal

Entidad: **Mancomunitat de L'Alcoià i El Comtat** (`mancomunitat-de-lalcoia-i-el-comtat`) — Comunitat Valenciana, comarcas Alcoià y El Comtat. Boletín: `dogv` (1 aviso).

## Contexto

No es un municipio unitario sino una **mancomunitat** de 13 municipios: Agres, Alcoi, Alcoleja, Alfafara, Banyeres de Mariola, Beniarrés, Alcosser de Planes, Quatretondeta, Cocentaina, Gorga, l'Alqueria d'Asnar, Millena y Muro. Los estatutos contemplan ordenación del territorio entre sus finalidades, pero el portal web actual se centra en **servicios compartidos** (transporte universitario STU, turismo, cultura, joventut, promoción económica, protección animal, igualdad), no en expedientes de planeamiento ni licencias de obra de los ayuntamientos miembros.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal principal | https://lamancomunitat.org |
| La Mancomunitat | https://lamancomunitat.org/la-mancomunitat/ |
| Qui som (estatutos, organigrama) | https://lamancomunitat.org/quisom/ |
| Municipis | https://lamancomunitat.org/la-mancomunitat/municipis-mancomunitat-alcoia-comtat/ |
| Serveis | https://lamancomunitat.org/la-mancomunitat/serveis/ |
| Xarxa Xaloc (ayudas vivienda jovenes) | https://lamancomunitat.org/xarxa-xaloc/ |
| Transport universitari STU | https://lamancomunitat.org/transport-universitari-stu/ |
| Sede electrónica | https://mancomunitatalcoiaicomtat.sedelectronica.es (indeterminada) |

## Cómo se listan expedientes / planeamiento

- **CMS:** WordPress (tema Divi / lamancomunitat).
- **Sin sección de urbanismo** ni tablón de expedientes urbanísticos en el portal.
- **PDFs relevantes** enlazados desde páginas de servicios:
  - Convocatoria DOGV ayudas vivienda jóvenes (`dogv.gva.es/.../2023_2823.pdf`) desde Xarxa Xaloc.
  - Plan VERDEA (ayudas energéticas) y requisitos adquisición vivienda.
  - Plànol parades campus UA (transporte universitario; no es planeamiento urbanístico parcelario).
- **Sede electrónica:** responde «Sede Electrónica Indeterminada» (sin tablón ni dossier de trámites urbanísticos).
- **REST API WordPress:** bloqueada por Kadence Security (401).

## Licencias de obra

- **Sin dataset** de licencias concedidas.
- **Sin trámites** de licencia de obra en el catálogo de la mancomunitat (servicios sociales, transporte, turismo, empleo).
- Las licencias urbanísticas corresponden a los **13 ayuntamientos miembros** (Alcoi, Cocentaina, Muro, etc.), no a la mancomunitat.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - Portal lamancomunitat.org: sin visor urbanístico ni datos abiertos GIS.
  - Sede electrónica: no operativa (página de selección).
  - ICV terramapas (`terramapas.icv.gva.es/0702_Planeamiento`): capas por municipio INE individual (03009 Alcoi, 03046 Cocentaina, etc.), no por mancomunitat; sin enlace a expedientes de la entidad supramunicipal.
  - Ayuntamiento de Alcoi (`alcoi.org/es/areas/urbanismo/`): PGOU 1989 y PGE preliminar con PDFs y planos, pero pertenecen al municipio de Alcoi, no a la mancomunitat.
- **Estrategia:** no hay query por código de expediente ni WFS/ArcGIS de la mancomunitat. El orquestador aplicará centroide de Alcoi + jitter.
- **Limitaciones:** entidad supramunicipal; planeamiento urbanístico municipal no agregado en un único portal.

## Limitaciones generales

- Portal orientado a turismo, cultura, joventut y servicios compartidos; urbanismo limitado a convocatorias de vivienda y planes de ayudas.
- Sede electrónica sin configurar.
- Sin licencias ni expedientes urbanísticos publicados en listado scrapeable.
- El aviso DOGV probablemente corresponde a la convocatoria de ayudas vivienda jóvenes (2023), no a un sector con polígono.
