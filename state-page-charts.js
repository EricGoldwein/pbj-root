/**
 * State page charts: load chart data from API and draw Chart.js line charts (time-scale x-axis).
 * Smart x-axis: year at Q1 only; quarter labels when range < 2 years; responsive tick count.
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

      function quarterToDate(q) {
        var s = String(q).trim();
        if (s.length < 5) return null;
        var y = parseInt(s.substring(0, 4), 10);
        var rest = (s.substring(4) || "").replace(/^Q?/i, "").trim();
        var qn = (rest === "1" || rest === "Q1") ? 1 : (rest === "2" || rest === "Q2") ? 2 : (rest === "3" || rest === "Q3") ? 3 : (rest === "4" || rest === "Q4") ? 4 : 1;
        return new Date(y, (qn - 1) * 3, 1);
      }

      function buildTimeSeriesData(quarters, values) {
        if (!quarters || !quarters.length) return [];
        var out = [];
        for (var i = 0; i < quarters.length; i++) {
          var dt = quarterToDate(quarters[i]);
          out.push({ x: dt ? dt.getTime() : null, y: (values && i < values.length) ? values[i] : null });
        }
        return out;
      }

      function getSpanYears(quarters) {
        if (!quarters || quarters.length < 2) return 1;
        var first = quarterToDate(quarters[0]);
        var last = quarterToDate(quarters[quarters.length - 1]);
        return first && last ? (last.getFullYear() - first.getFullYear()) + (last.getMonth() - first.getMonth()) / 12 : 1;
      }

      function timeTickCallback(quarters) {
        var spanYears = getSpanYears(quarters);
        var showQuarters = spanYears < 2;
        return function(value) {
          var date = new Date(value);
          if (showQuarters) {
            var y = date.getFullYear();
            var q = Math.floor(date.getMonth() / 3) + 1;
            return y + " Q" + q;
          }
          if (date.getMonth() !== 0 || date.getDate() !== 1) return "";
          return "" + date.getFullYear();
        };
      }

      function makeLineTime(id, quarters, datasets, yTitle, directCareSuffix, integerFormat) {
        var ctx = document.getElementById(id);
        if (!ctx || !quarters || !quarters.length) return;
        var spanYears = getSpanYears(quarters);
        var maxTicks = window.innerWidth < 768 ? Math.min(12, Math.max(6, Math.ceil(spanYears) + 1)) : Math.min(15, Math.max(6, Math.ceil(spanYears) + 2));
        var timeDatasets = datasets.map(function(ds) {
          return {
            label: ds.label,
            data: buildTimeSeriesData(quarters, ds.data),
            borderColor: ds.borderColor,
            borderDash: ds.borderDash || undefined,
            tension: ds.tension !== undefined ? ds.tension : 0.3,
            fill: false,
            spanGaps: false
          };
        });
        var formatValue = integerFormat
          ? function(v) { return (typeof v === "number" && !isNaN(v)) ? Math.round(v).toLocaleString() : (v != null ? String(v) : ""); }
          : function(v) { return (typeof v === "number" && !isNaN(v)) ? (Math.round(v * 100) / 100).toFixed(2) : (v != null ? v : ""); };
        new Chart(ctx.getContext("2d"), {
          type: "line",
          data: { datasets: timeDatasets },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { labels: { color: textColor, boxWidth: 14, boxPadding: 3, font: { size: 11 } } },
              tooltip: {
                callbacks: {
                  title: function(context) {
                    if (context[0] && context[0].raw && context[0].raw.x != null) {
                      var date = new Date(context[0].raw.x);
                      return date.getFullYear() + " Q" + (Math.floor(date.getMonth() / 3) + 1);
                    }
                    return "";
                  },
                  label: function(context) {
                    var v = context.parsed.y;
                    return context.dataset.label + ": " + formatValue(v);
                  },
                  afterBody: function(tooltipItems) {
                    if (!directCareSuffix) return null;
                    var hasDirect = tooltipItems.some(function(t) {
                      return ((t.dataset && t.dataset.label) || "").indexOf("Direct") !== -1;
                    });
                    return hasDirect ? [directCareSuffix] : null;
                  }
                }
              }
            },
            scales: {
              y: {
                beginAtZero: false,
                ticks: {
                  color: textColor,
                  callback: integerFormat ? function(value) {
                    var n = Number(value);
                    if (!isFinite(n)) return value;
                    return Math.round(n).toLocaleString(undefined, { maximumFractionDigits: 0 });
                  } : undefined
                },
                grid: { color: gridColor },
                title: { display: !!yTitle, text: yTitle || "", color: textColor }
              },
              x: {
                type: "time",
                time: {
                  unit: "quarter",
                  displayFormats: { year: "yyyy", quarter: "yyyy Qq", month: "MMM yyyy" },
                  tooltipFormat: "yyyy Qq"
                },
                ticks: {
                  color: textColor,
                  maxTicksLimit: maxTicks,
                  autoSkip: true,
                  font: { size: 11 },
                  callback: timeTickCallback(quarters)
                },
                grid: { color: gridColor }
              }
            }
          }
        });
      }

      var quarters = d.raw_quarters;
      var directCareTip = "Via MACPAC; estimate.";
      if (d.total && d.total.length) {
        var ds = [
          { label: "Total", data: d.total, borderColor: "#1e40af", tension: 0.3, fill: false, spanGaps: false },
          { label: "Direct", data: d.direct || [], borderColor: "#6366f1", borderDash: [5, 5], tension: 0.3, fill: false, spanGaps: false }
        ];
        makeLineTime("stateChartTotal", quarters, ds, "Hours per resident day", directCareTip);
      }
      if (d.rn && d.rn.length) {
        var rnDs = [
          { label: "Total RN", data: d.rn, borderColor: "#1e40af", tension: 0.3, fill: false, spanGaps: false }
        ];
        if (d.rn_care && d.rn_care.length) {
          rnDs.push({ label: "RN (excl. Admin/DON)", data: d.rn_care, borderColor: "#6366f1", borderDash: [5, 5], tension: 0.3, fill: false, spanGaps: false });
        }
        makeLineTime("stateChartRN", quarters, rnDs, "Hours per resident day", directCareTip);
      }
      if (d.census && d.census.length) {
        makeLineTime("stateChartCensus", quarters, [
          { label: "Resident census", data: d.census, borderColor: "#1e40af", tension: 0.3, fill: false, spanGaps: false }
        ], "Resident census", null, true);
      }
      if (d.contract && d.contract.length) {
        makeLineTime("stateChartContract", quarters, [
          { label: "Contract %", data: d.contract, borderColor: "#1e40af", tension: 0.3, fill: false, spanGaps: false }
        ], "Contract %", null);
      }
    })
    .catch(function(e) { console.warn("State chart data not available", e); });
})();
