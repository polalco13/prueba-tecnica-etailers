"use strict";

// El servidor calcula los importes. Number se usa únicamente para dibujar.
const source = document.getElementById("chart-data");
if (source && typeof Chart !== "undefined") {
  const values = JSON.parse(source.textContent);
  new Chart(document.getElementById("sales-chart"), {
    type: "bar",
    data: {
      labels: values.labels,
      datasets: [
        {label: "Facturación (importe)", data: values.revenue.map(Number),
          backgroundColor: "#b2d8d0", hoverBackgroundColor: "#5baca0", borderRadius: 3,
          yAxisID: "revenue", order: 2},
        {label: "Unidades vendidas", data: values.units, type: "line",
          borderColor: "#244b68", backgroundColor: "#244b68", pointRadius: 3,
          tension: 0, yAxisID: "units", order: 1},
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      interaction: {mode: "index", intersect: false},
      plugins: {legend: {position: "bottom"}},
      scales: {
        x: {grid: {display: false}, ticks: {maxRotation: 60}},
        revenue: {position: "left", beginAtZero: true,
          title: {display: true, text: "Facturación · importe de origen"}},
        units: {position: "right", beginAtZero: true, grid: {drawOnChartArea: false},
          title: {display: true, text: "Unidades vendidas"}, ticks: {precision: 0}},
      },
    },
  });
  document.getElementById("chart-fallback").textContent =
    "Último mes parcial. Consulta la tabla para ver los importes exactos.";
}
