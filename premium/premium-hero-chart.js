/**
 * Premium landing — demo compliance chart (CCN 320365, CMS PBJ–style).
 * Data: demo/320365-compliance-data.json (sourced from public PBJ daily totals).
 */
(function () {
    var FACILITY_LABEL = "Phoebe J. Nursing & Rehabilitation Center";
    var PANEL_TITLE = "Total HPRD";
    var LINE_COLOR = "#1e3a5f";
    var DATA_URLS = [
        "demo/320365-compliance-data.json",
        "/premium/demo/320365-compliance-data.json",
    ];

    function dowLong(ymd) {
        var m = String(ymd || "").slice(0, 10).match(/^(\d{4})-(\d{2})-(\d{2})$/);
        if (!m) return "";
        var d = new Date(parseInt(m[1], 10), parseInt(m[2], 10) - 1, parseInt(m[3], 10));
        if (isNaN(d.getTime())) return "";
        return d.toLocaleDateString("en-US", { weekday: "long" });
    }

    function renderChart(el, payload, opts) {
        if (!el || typeof Plotly === "undefined" || !payload || !payload.rows || !payload.rows.length) {
            return;
        }
        opts = opts || {};
        var rows = payload.rows;
        var thr = parseFloat(payload.threshold);
        if (!Number.isFinite(thr)) thr = 3.5;
        var dates = rows.map(function (r) { return r.date; });
        var vals = rows.map(function (r) { return r.hprd; });
        var met = rows.map(function (r) { return !!r.met; });
        var thrLine = Array(dates.length).fill(thr);
        var stateName = payload.state || "";
        var subtitleRule = "Estimated state threshold: " + thr.toFixed(2) + " HPRD";
        var sub = [stateName, subtitleRule].filter(Boolean).join(" · ");

        var markerSz = vals.map(function (v, i) {
            return v == null || !Number.isFinite(v) ? 0 : met[i] ? 4 : 11;
        });
        var markerCol = vals.map(function (v, i) {
            return v == null || !Number.isFinite(v) ? "rgba(0,0,0,0)" : met[i] ? LINE_COLOR : "#b91c1c";
        });
        var markerLineW = vals.map(function (v, i) {
            return v == null || !Number.isFinite(v) ? 0 : met[i] ? 0 : 2;
        });
        var markerLineCol = vals.map(function (v, i) {
            return v == null || !Number.isFinite(v) ? LINE_COLOR : met[i] ? LINE_COLOR : "#fef2f2";
        });
        var hoverWhen = rows.map(function (r) {
            var w = dowLong(r.date);
            return w ? w + ", " + r.date : r.date;
        });
        var hoverStatus = rows.map(function (r) {
            return r.met ? "At or above reference for this rule." : "Below reference for this rule.";
        });

        var traces = [
            {
                x: dates,
                y: vals,
                customdata: hoverWhen,
                type: "scatter",
                mode: "lines+markers",
                name: "Total HPRD",
                line: { color: LINE_COLOR, width: 2.75 },
                connectgaps: true,
                marker: {
                    size: markerSz,
                    color: markerCol,
                    line: { width: markerLineW, color: markerLineCol },
                },
                text: hoverStatus,
                hovertemplate:
                    "<b>%{customdata}</b><br>HPRD: %{y:.2f}<br>%{text}<extra></extra>",
            },
            {
                x: dates,
                y: thrLine,
                type: "scatter",
                mode: "lines",
                name: "Reference",
                showlegend: false,
                line: { color: "#64748b", width: 2, dash: "dash" },
                hoverinfo: "skip",
            },
        ];

        var layout = {
            title: {
                text:
                    '<span style="font-size:0.95em;font-weight:700;color:#0f172a;">' +
                    PANEL_TITLE +
                    '</span><br><span style="font-size:0.72em;font-weight:400;color:#475569;">' +
                    FACILITY_LABEL +
                    (sub ? " · " + sub : "") +
                    "</span>",
                font: { family: "system-ui, Segoe UI, Roboto, Helvetica, Arial, sans-serif" },
                x: 0.5,
                xanchor: "center",
                y: 0.99,
                yanchor: "top",
                pad: { t: 10, b: 4 },
            },
            xaxis: {
                showgrid: true,
                gridcolor: "#e2e8f0",
                zeroline: false,
                tickfont: { size: opts.compact ? 8 : 10, color: "#334155" },
                nticks: opts.compact ? 6 : 10,
            },
            yaxis: {
                title: { text: "HPRD", font: { size: opts.compact ? 10 : 11, color: "#475569" } },
                showgrid: true,
                gridcolor: "#f1f5f9",
                zeroline: true,
                zerolinecolor: "#cbd5e1",
                rangemode: "tozero",
                tickfont: { size: opts.compact ? 8 : 10, color: "#334155" },
            },
            hovermode: "closest",
            showlegend: true,
            legend: {
                orientation: "h",
                yanchor: "top",
                y: -0.12,
                xanchor: "center",
                x: 0.5,
                font: { size: 10, color: "#475569" },
            },
            margin: opts.compact
                ? { l: 44, r: 12, t: 56, b: 48 }
                : { l: 52, r: 16, t: 64, b: 56 },
            paper_bgcolor: "#ffffff",
            plot_bgcolor: "#ffffff",
            annotations: [
                {
                    text:
                        '<span style="font-size:9px;color:#64748b;">Source: CMS PBJ · 320 Consulting · Demo CCN 320365 (illustrative)</span>',
                    showarrow: false,
                    xref: "paper",
                    yref: "paper",
                    x: 0.5,
                    y: -0.22,
                    xanchor: "center",
                },
            ],
            autosize: true,
        };

        var config = {
            responsive: true,
            displayModeBar: false,
            staticPlot: !!opts.staticPlot,
        };

        Plotly.newPlot(el, traces, layout, config);
    }

    function fetchData() {
        function attempt(i) {
            if (i >= DATA_URLS.length) {
                return Promise.reject(new Error("No compliance data"));
            }
            return fetch(DATA_URLS[i], { cache: "default" })
                .then(function (res) {
                    if (!res.ok) throw new Error("HTTP " + res.status);
                    return res.json();
                })
                .catch(function () {
                    return attempt(i + 1);
                });
        }
        return attempt(0);
    }

    function init() {
        var main = document.getElementById("pbj-audit-hero-chart");
        var bg = document.getElementById("pbj-audit-hero-chart-bg");
        if (!main) return;

        fetchData()
            .then(function (payload) {
                var under = payload.rows.filter(function (r) { return !r.met; }).length;
                var total = payload.rows.length;
                var stat = document.getElementById("pbj-audit-hero-chart-stat");
                if (stat && total) {
                    stat.textContent =
                        under + " of " + total + " days below " + payload.threshold.toFixed(2) + " HPRD (demo window)";
                }
                renderChart(main, payload, { staticPlot: false });
                if (bg) {
                    renderChart(bg, payload, { compact: true, staticPlot: true });
                }
            })
            .catch(function () {
                main.innerHTML =
                    '<p class="small text-muted text-center p-4 mb-0">Chart preview unavailable.</p>';
            });
    }

    window.addEventListener("load", init);
})();
