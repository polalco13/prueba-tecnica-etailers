"use strict";

// El servidor calcula los importes. Number se usa únicamente para dibujar.
const source = document.getElementById("chart-data");
if (source && typeof Chart !== "undefined") {
  const values = JSON.parse(source.textContent);
  document.querySelector(".chart-wrap").hidden = false;
  new Chart(document.getElementById("sales-chart"), {
    type: "bar",
    data: {
      labels: values.labels,
      datasets: [
        {label: "Facturación (importe)", data: values.revenue.map(Number),
          backgroundColor: "#498878", hoverBackgroundColor: "#14695e", borderRadius: 3,
          yAxisID: "revenue", order: 2},
        {label: "Unidades vendidas", data: values.units, type: "line",
          borderColor: "#244b68", backgroundColor: "#244b68", pointRadius: 3, borderWidth: 2,
          tension: 0, yAxisID: "units", order: 1},
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false, locale: "es-ES",
      color: "#586c66", font: {family: "system-ui, sans-serif"},
      interaction: {mode: "index", intersect: false},
      plugins: {legend: {position: "bottom", labels: {boxWidth: 16, boxHeight: 10, padding: 16}}},
      scales: {
        x: {grid: {display: false}, ticks: {maxRotation: 45}},
        revenue: {position: "left", beginAtZero: true,
          grid: {color: "#e5ebe7"},
          title: {display: true, text: "Facturación · importe de origen"}},
        units: {position: "right", beginAtZero: true, grid: {drawOnChartArea: false},
          title: {display: true, text: "Unidades vendidas"}, ticks: {precision: 0}},
      },
    },
  });
  document.getElementById("chart-fallback").textContent =
    "Último mes parcial. Consulta la tabla para ver los importes exactos.";
}
