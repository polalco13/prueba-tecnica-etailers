# Chart.js local

Versión fijada: **4.5.1**, licencia MIT incluida en `Chart.js-LICENSE.md`.
Se usa el bundle UMD para dibujar las series ya calculadas por SQL, sin Node,
bundler ni peticiones externas desde el navegador. La biblioteca estándar no
incluye un gráfico interactivo con ejes, leyenda y tooltips; esta es la única
dependencia JavaScript añadida en F9, prevista en TECH_SPEC.

Origen: paquete oficial `https://registry.npmjs.org/chart.js/-/chart.js-4.5.1.tgz`,
archivos `package/dist/chart.umd.min.js` y `package/LICENSE.md` sin modificaciones.
Se verificó el SHA-512 del tarball contra `dist.integrity` de su metadata npm.
SHA-256 del bundle: `48444a82d4edcb5bec0f1965faacdde18d9c17db3063d042abada2f705c9f54a`.

Referencias: [release](https://github.com/chartjs/Chart.js/releases/tag/v4.5.1),
[integración UMD](https://www.chartjs.org/docs/latest/getting-started/integration.html).
No se necesita acceder a esos enlaces al ejecutar el panel.
