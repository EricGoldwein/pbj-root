/**
 * State page charts: load chart data from API and draw Chart.js line charts.
 * No inline script on state page = no brace/syntax errors.
 */
(function() {
  var meta = document.getElementById("state-chart-meta");
  if (!meta) return;
  var stateCode = (meta.getAttribute("data-state-code") || "").trim();
  if (!stateCode) return;
  fetch("/api/state/" + encodeURIComponent(stateCode) + "/chart-data")
    .then(function(r) { return r.ok ? r.json() : Promise.reject(new Error("no data")); })
    .then(function(d) {
      if (!d || !d.raw_quarters || !d.raw_quarters.length) return;
      var textColor = "rgba(226,232,240,0.9)";
      var gridColor = "rgba(148,163,184,0.2)";
      if (typeof Chart !== "undefined") { Chart.defaults.color = textColor; Chart.defaults.borderColor = gridColor; }
      function xLabels(quarters) {
        if (!quarters || !quarters.length) return [];
        return quarters.map(function(q, i) {
          var y = String(q).substring(0,4), qtr = String(q).substring(4);
          if (qtr === "Q1") return y;
          var prev = i > 0 ? quarters[i-1] : null;
          if (prev && String(prev).substring(0,4) !== y) return y;
          return "";
        });
      }
      function makeLine(id, labels, datasets, yTitle, directCareSuffix) {
        var ctx = document.getElementById(id);
        if (!ctx || !d.raw_quarters || !d.raw_quarters.length) return;
        new Chart(ctx.getContext("2d"), {
          type: "line",
          data: { labels: labels, datasets: datasets },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { labels: { color: textColor } },
              tooltip: {
                callbacks: {
                  title: function(c) { var q = d.raw_quarters[c[0].dataIndex]; return q ? (q.substring(5) + " " + q.substring(0,4)) : ""; },
                  afterBody: function(tooltipItems) {
                    if (!directCareSuffix) return null;
                    var hasDirect = tooltipItems.some(function(t) { return (datasets[t.datasetIndex] && datasets[t.datasetIndex].label || "").indexOf("Direct Care") !== -1; });
                    return hasDirect ? directCareSuffix : null;
                  }
                }
              }
            },
            scales: { y: { beginAtZero: false, ticks: { color: textColor }, grid: { color: gridColor }, title: { display: !!yTitle, text: yTitle || "", color: textColor } }, x: { ticks: { color: textColor, maxTicksLimit: 12 }, grid: { color: gridColor } } }
          }
        });
      }
      var labels = xLabels(d.raw_quarters);
      var directCareTip = " (excludes admin, DON)";
      if (d.total && d.total.length) {
        var ds = [ { label: "Total HPRD", data: d.total, borderColor: "#1e40af", tension: 0.3, fill: false, spanGaps: false }, { label: "Direct Care HPRD", data: d.direct || [], borderColor: "#6366f1", borderDash: [5,5], tension: 0.3, fill: false, spanGaps: false } ];
        makeLine("stateChartTotal", labels, ds, "Hours per resident day", directCareTip);
      }
      if (d.rn && d.rn.length) {
        var rnDs = [ { label: "RN HPRD", data: d.rn, borderColor: "#1e40af", tension: 0.3, fill: false, spanGaps: false } ];
        if (d.rn_care && d.rn_care.length) rnDs.push({ label: "RN Direct Care HPRD", data: d.rn_care, borderColor: "#6366f1", borderDash: [5,5], tension: 0.3, fill: false, spanGaps: false });
        makeLine("stateChartRN", labels, rnDs, "Hours per resident day", directCareTip);
      }
      if (d.census && d.census.length) makeLine("stateChartCensus", labels, [ { label: "Avg daily census", data: d.census, borderColor: "#1e40af", tension: 0.3, fill: false, spanGaps: false } ], "Census");
      if (d.contract && d.contract.length) makeLine("stateChartContract", labels, [ { label: "Contract %", data: d.contract, borderColor: "#1e40af", tension: 0.3, fill: false, spanGaps: false } ], "Contract %");
    })
    .catch(function(e) { console.warn("State chart data not available", e); });
})();
