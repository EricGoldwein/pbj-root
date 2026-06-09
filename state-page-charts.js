/**
 * State page charts: load chart data from API and draw Chart.js line charts (time-scale x-axis).
 * RN staffing chart supports RN / LPN / Nurse aide tabs (aide: single series).
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
      var textColor = "rgba(226, 232, 240, 0.95)";
      var gridColor = "rgba(51, 65, 85, 0.55)";
      var axisColor = "rgba(148, 163, 184, 0.58)";
      if (typeof Chart !== "undefined") { Chart.defaults.color = textColor; Chart.defaults.borderColor = axisColor; }

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
        return function(value, index, ticks) {
          var date = new Date(value);
          if (showQuarters) {
            var y = date.getFullYear();
            var q = Math.floor(date.getMonth() / 3) + 1;
            return y + " Q" + q;
          }
          var y = date.getFullYear();
          if (typeof index !== "number" || index === 0) return "" + y;
          if (!ticks || !ticks[index - 1]) return "";
          var prevY = ticks[index - 1].value != null ? new Date(ticks[index - 1].value).getFullYear() : null;
          if (prevY !== y) return "" + y;
          return "";
        };
      }

      function trimTrailingZeros(s) {
        return String(s).replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "");
      }

      function normalizeValueFormat(arg) {
        if (arg === true || arg === "count") return "count";
        if (arg === "percent") return "percent";
        return "hprd";
      }

      /** Y-axis tick labels — compact for large counts, metric-aware elsewhere. */
      function formatAxisValue(n, kind) {
        n = Number(n);
        if (!isFinite(n)) return n != null ? String(n) : "";
        if (kind === "percent") {
          if (Math.abs(n) >= 10) return Math.round(n) + "%";
          return trimTrailingZeros(n.toFixed(1)) + "%";
        }
        if (kind === "count") {
          var sign = n < 0 ? "-" : "";
          var abs = Math.abs(n);
          if (abs >= 1e9) return sign + trimTrailingZeros((abs / 1e9).toFixed(2)) + "B";
          if (abs >= 1e6) return sign + trimTrailingZeros((abs / 1e6).toFixed(2)) + "M";
          if (abs >= 1e4) {
            var k = abs / 1e3;
            return sign + (k >= 100 ? String(Math.round(k)) : trimTrailingZeros(k.toFixed(1))) + "K";
          }
          if (abs >= 1e3) return sign + Math.round(abs).toLocaleString(undefined, { maximumFractionDigits: 0 });
          return sign + String(Math.round(abs));
        }
        return trimTrailingZeros((Math.round(n * 100) / 100).toFixed(2));
      }

      /** Line charts: hide points at rest; show on hover (matches total/contract interaction). */
      function withLineHoverPoints(ds) {
        var color = ds.borderColor || "#2dd4bf";
        return {
          pointRadius: 0,
          pointHoverRadius: 5,
          pointHitRadius: 12,
          pointBackgroundColor: color,
          pointBorderColor: color,
          pointBorderWidth: 2
        };
      }

      /** Tooltip values — full precision for counts; metric-aware elsewhere. */
      function formatTooltipValue(n, kind) {
        n = Number(n);
        if (!isFinite(n)) return n != null ? String(n) : "";
        if (kind === "percent") return trimTrailingZeros(n.toFixed(2)) + "%";
        if (kind === "count") return Math.round(n).toLocaleString(undefined, { maximumFractionDigits: 0 });
        return (Math.round(n * 100) / 100).toFixed(2);
      }

      function makeLineTime(id, quarters, datasets, yTitle, directCareSuffix, valueFormat, extraScales) {
        var ctx = document.getElementById(id);
        if (!ctx || !quarters || !quarters.length) return;
        var spanYears = getSpanYears(quarters);
        var maxTicks = window.innerWidth < 768 ? Math.min(12, Math.max(6, Math.ceil(spanYears) + 1)) : Math.min(15, Math.max(6, Math.ceil(spanYears) + 2));
        var timeDatasets = datasets.map(function(ds) {
          var row = {
            label: ds.label,
            data: buildTimeSeriesData(quarters, ds.data),
            borderColor: ds.borderColor,
            borderDash: ds.borderDash || undefined,
            tension: ds.tension !== undefined ? ds.tension : 0.3,
            fill: false,
            spanGaps: false
          };
          Object.assign(row, withLineHoverPoints(ds));
          if (ds.yAxisID) row.yAxisID = ds.yAxisID;
          return row;
        });
        var metricKind = normalizeValueFormat(valueFormat);
        var formatValue = function(v) {
          if (typeof v !== "number" || isNaN(v)) return v != null ? String(v) : "";
          return formatTooltipValue(v, metricKind);
        };
        var scales = {
          y: {
            position: "left",
            beginAtZero: false,
            ticks: {
              color: textColor,
              callback: function(value) {
                return formatAxisValue(value, metricKind);
              }
            },
            grid: { color: gridColor },
            border: { color: axisColor, width: 1 },
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
            grid: { color: gridColor },
            border: { color: axisColor, width: 1 }
          }
        };
        if (extraScales) {
          Object.keys(extraScales).forEach(function(k) { scales[k] = extraScales[k]; });
        }
        new Chart(ctx.getContext("2d"), {
          type: "line",
          data: { datasets: timeDatasets },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
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
                      return ((t.dataset && t.dataset.label) || "").indexOf("Direct") !== -1
                        || ((t.dataset && t.dataset.label) || "").indexOf("excl.") !== -1;
                    });
                    return hasDirect ? [directCareSuffix] : null;
                  }
                }
              }
            },
            scales: scales
          }
        });
      }

      function staffingRoleChartTitle(role) {
        var compact = typeof window !== "undefined" && window.innerWidth < 768;
        if (role === "lpn") return compact ? "LPN staff" : "LPN Staffing";
        if (role === "aide") return compact ? "Aide staff" : "Nurse Aide Staffing";
        return compact ? "RN staff" : "RN Staffing";
      }
      function aideChartLegendLabel() {
        if (typeof window !== "undefined" && window.innerWidth < 768) {
          return "Aide (CNA, NAt, MedAide)";
        }
        return "Aide (CNA, aide-in-training, MedAide)";
      }
      function updateStaffingRoleChartChrome(canvasId, tabsId, role) {
        var tabs = document.getElementById(tabsId);
        var container = tabs ? tabs.closest(".pbj-staffing-role-chart") : null;
        if (!container) return;
        var title = staffingRoleChartTitle(role);
        var suffix = container.getAttribute("data-title-suffix") || "";
        var statePrefix = container.getAttribute("data-state-prefix") || "";
        var oneline = container.querySelector(".pbj-staffing-role-title-oneline");
        var main = container.querySelector(".pbj-staffing-role-title-main");
        var mobile = container.querySelector(".pbj-staffing-role-title-mobile");
        if (oneline) oneline.textContent = title + suffix;
        if (main) main.textContent = title;
        if (mobile) mobile.textContent = statePrefix + title;
      }
      function initStaffingRoleChart(canvasId, tabsId, payload, quarters) {
        var ctx = document.getElementById(canvasId);
        if (!ctx || !quarters || !quarters.length) return;
        var chart = null;
        var directCareTip = "Via MACPAC; estimate.";
        function roleDatasets(role) {
          if (role === "rn") {
            var ds = [{ label: "Total RN", data: payload.rn || [], borderColor: "#2dd4bf", tension: 0.3, fill: false, spanGaps: false }];
            if (payload.rn_care && payload.rn_care.length) {
              ds.push({ label: "RN (excl. Admin/DON)", data: payload.rn_care, borderColor: "rgba(161,161,170,0.9)", borderDash: [6, 4], tension: 0.3, fill: false, spanGaps: false });
            }
            return ds;
          }
          if (role === "lpn") {
            var ds2 = [{ label: "Total LPN", data: payload.lpn || [], borderColor: "#2dd4bf", tension: 0.3, fill: false, spanGaps: false }];
            if (payload.lpn_care && payload.lpn_care.length) {
              ds2.push({ label: "LPN (excl. Admin)", data: payload.lpn_care, borderColor: "rgba(161,161,170,0.9)", borderDash: [6, 4], tension: 0.3, fill: false, spanGaps: false });
            }
            return ds2;
          }
          return [{ label: aideChartLegendLabel(), data: payload.aide || [], borderColor: "#2dd4bf", tension: 0.3, fill: false, spanGaps: false }];
        }
        function drawRole(role) {
          var datasets = roleDatasets(role);
          if (!datasets.length) return;
          updateStaffingRoleChartChrome(canvasId, tabsId, role);
          var spanYears = getSpanYears(quarters);
          var maxTicks = window.innerWidth < 768 ? Math.min(12, Math.max(6, Math.ceil(spanYears) + 1)) : Math.min(15, Math.max(6, Math.ceil(spanYears) + 2));
          var timeDatasets = datasets.map(function(ds) {
            var row = {
              label: ds.label,
              borderColor: ds.borderColor,
              borderDash: ds.borderDash,
              tension: ds.tension !== undefined ? ds.tension : 0.3,
              fill: false,
              spanGaps: false,
              data: buildTimeSeriesData(quarters, ds.data)
            };
            return Object.assign(row, withLineHoverPoints(ds));
          });
          var opts = {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
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
                    if (typeof v === "number" && !isNaN(v)) return context.dataset.label + ": " + formatTooltipValue(v, "hprd");
                    return context.dataset.label + ": " + (v != null ? v : "");
                  },
                  afterBody: function(tooltipItems) {
                    var hasDirect = tooltipItems.some(function(t) {
                      var lbl = (t.dataset && t.dataset.label) || "";
                      return lbl.indexOf("Direct") !== -1 || lbl.indexOf("excl.") !== -1 || lbl.indexOf("direct care") !== -1;
                    });
                    return hasDirect ? [directCareTip] : null;
                  }
                }
              }
            },
            scales: {
              y: {
                beginAtZero: false,
                ticks: {
                  color: textColor,
                  callback: function(value) { return formatAxisValue(value, "hprd"); }
                },
                grid: { color: gridColor },
                border: { color: axisColor, width: 1 },
                title: { display: true, text: "Hours per resident day", color: textColor }
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
                grid: { color: gridColor },
                border: { color: axisColor, width: 1 }
              }
            }
          };
          if (chart) {
            chart.data.datasets = timeDatasets;
            chart.update();
            return;
          }
          chart = new Chart(ctx.getContext("2d"), { type: "line", data: { datasets: timeDatasets }, options: opts });
        }
        drawRole("rn");
        var tabs = document.getElementById(tabsId);
        if (tabs) {
          tabs.querySelectorAll(".pbj-staffing-role-tab").forEach(function(btn) {
            btn.addEventListener("click", function() {
              var role = btn.getAttribute("data-role") || "rn";
              tabs.querySelectorAll(".pbj-staffing-role-tab").forEach(function(b) {
                var on = b === btn;
                b.classList.toggle("is-active", on);
                b.setAttribute("aria-selected", on ? "true" : "false");
              });
              drawRole(role);
            });
          });
        }
      }

      var quarters = d.raw_quarters;
      var directCareTip = "Via MACPAC; estimate.";
      if (d.total && d.total.length) {
        var ds = [
          { label: "Total", data: d.total, borderColor: "#2dd4bf", tension: 0.3, fill: false, spanGaps: false },
          { label: "Direct", data: d.direct || [], borderColor: "rgba(161,161,170,0.9)", borderDash: [6, 4], tension: 0.3, fill: false, spanGaps: false }
        ];
        makeLineTime("stateChartTotal", quarters, ds, "Hours per resident day", directCareTip);
      }
      if (d.rn && d.rn.length) {
        initStaffingRoleChart("stateChartRN", "stateStaffingRoleTabs", d, quarters);
      }
      if (d.census && d.census.length) {
        makeLineTime("stateChartCensus", quarters, [
          { label: "Resident census", data: d.census, borderColor: "#2dd4bf", tension: 0.3, fill: false, spanGaps: false }
        ], "Census", null, "count");
      }
      if (d.contract && d.contract.length) {
        makeLineTime("stateChartContract", quarters, [
          { label: "Contract %", data: d.contract, borderColor: "#2dd4bf", tension: 0.3, fill: false, spanGaps: false }
        ], "Contract %", null, "percent");
      }
    })
    .catch(function(e) { console.warn("State chart data not available", e); });
})();
