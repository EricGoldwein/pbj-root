/**

 * Premium hub — CCN/provider combobox, dashboard request POST.

 * Endpoint: <meta name="pbj-premium-booking-url" content="...">

 * Facility names: premium-nursing-homes.json (from ProviderInfoNorm; regenerate as needed).

 */

(function () {

    function strip(s) {

        return (s || "").trim();

    }



    function normalizeCcn(v) {

        return strip(v).replace(/\D/g, "").slice(0, 6);

    }



    function escapeHtml(s) {

        return String(s || "")

            .replace(/&/g, "&amp;")

            .replace(/</g, "&lt;")

            .replace(/>/g, "&gt;")

            .replace(/"/g, "&quot;");

    }



    function getBookingUrl() {

        var meta = document.querySelector('meta[name="pbj-premium-booking-url"]');

        return meta ? strip(meta.getAttribute("content")) : "";

    }



    var ENRICHED = {

        "335513": {

            demoHref: "/premium/335513",

            careCompareHref:

                "https://www.medicare.gov/care-compare/details/nursing-home/335513/view-all?state=NY",

        },

    };



    var LOOKUP = {};

    var NAME_TO_CCN = {};

    var PROVIDER_ROWS = [];



    function careCompareUrlForCcn(ccn) {

        return (

            "https://www.medicare.gov/care-compare/details/nursing-home/" +

            encodeURIComponent(ccn) +

            "/view-all"

        );

    }



    function buildIndexes(rows) {

        LOOKUP = {};

        NAME_TO_CCN = {};

        for (var i = 0; i < rows.length; i++) {

            var row = rows[i];

            var c = row.c;

            var n = row.n;

            if (!c || c.length !== 6 || !n) continue;

            LOOKUP[c] = { name: n };

            NAME_TO_CCN[n.toLowerCase()] = c;

        }

    }



    function getFacilityMeta(ccn) {

        var c = normalizeCcn(ccn);

        var row = LOOKUP[c];

        if (!row) return null;

        var en = ENRICHED[c] || {};

        return {

            name: row.name,

            demoHref: en.demoHref || "/premium/" + c,

            careCompareHref: en.careCompareHref || careCompareUrlForCcn(c),

        };

    }



    function resolveCcnFromInput(raw) {

        var s = strip(raw);

        if (!s) return "";

        var d = normalizeCcn(s);

        if (d.length === 6) return d;

        var hit = NAME_TO_CCN[s.toLowerCase()];

        return hit || "";

    }



    function isDigitOnlyQuery(t) {

        return /^[\d\s-]+$/.test(strip(t));

    }



    function filterRows(query) {

        var t = strip(query);

        if (!t) return [];

        var MAX = 45;

        var out = [];

        var used = {};

        function add(r) {

            if (out.length >= MAX || used[r.c]) return;

            used[r.c] = 1;

            out.push(r);

        }

        var d = normalizeCcn(t);

        var i;

        var r;

        if (d.length >= 1 && isDigitOnlyQuery(t)) {

            for (i = 0; i < PROVIDER_ROWS.length; i++) {

                r = PROVIDER_ROWS[i];

                if (r.c.indexOf(d) === 0) add(r);

            }

            return out;

        }

        if (t.length < 2) return [];

        var lower = t.toLowerCase();

        for (i = 0; i < PROVIDER_ROWS.length; i++) {

            r = PROVIDER_ROWS[i];

            if (r.n.toLowerCase().indexOf(lower) >= 0) add(r);

        }

        return out;

    }



    var ccnInput = document.getElementById("ccn");

    var auditFrom = document.getElementById("audit-from");

    var auditTo = document.getElementById("audit-to");

    var sandboxForm = document.getElementById("hub-rb-sandbox-form");

    var statusEl = document.getElementById("form-status");

    var hubEmail = document.getElementById("hub-pro-email");

    var hubConsultTimes = document.getElementById("hub-consult-times");

    var hubRequestType = document.getElementById("hub-request-type");

    var hubWebsite = document.getElementById("hub-website");

    var hubRequestFields = document.getElementById("hub-request-fields");

    var hubRequestSuccess = document.getElementById("hub-request-success");

    var hubRequestSuccessEmail = document.getElementById("hub-request-success-email");

    var submitBtn = document.getElementById("hub-generate-pdf-btn");



    var suggestPanel = document.getElementById("ccn-suggest-panel");

    var suggestList = document.getElementById("ccn-suggest-list");

    var uiWired = false;

    var suggestTimer = null;

    var blurTimer = null;

    var submitBtnDefaultHtml = submitBtn ? submitBtn.innerHTML : "";



    function setStatus(message, tone) {

        if (!statusEl) return;

        statusEl.textContent = message || "";

        statusEl.classList.remove("pbj-hub-form-status--error", "pbj-hub-form-status--success");

        if (tone === "error") statusEl.classList.add("pbj-hub-form-status--error");

        if (tone === "success") statusEl.classList.add("pbj-hub-form-status--success");

    }



    function showSuccess(emailVal) {

        if (hubRequestFields) hubRequestFields.hidden = true;

        if (hubRequestSuccess) {

            hubRequestSuccess.hidden = false;

            if (hubRequestSuccessEmail) hubRequestSuccessEmail.textContent = emailVal;

        }

        setStatus("", null);

        if (hubRequestSuccess) {

            try {

                hubRequestSuccess.focus();

            } catch (e) {}

        }

    }



    var DEFAULT_AUDIT_FROM = "2020-03-20";

    var DEFAULT_AUDIT_TO = "2025-12-31";



    function isDesktopDates() {

        return window.matchMedia("(min-width: 768px)").matches;

    }



    function postPremiumRequest(payload, onDone) {

        var bookingUrl = getBookingUrl();

        if (!bookingUrl) {

            onDone("Request service is not configured. Please try again later.", "error");

            return;

        }

        fetch(bookingUrl, {

            method: "POST",

            headers: {

                Accept: "application/json",

                "Content-Type": "application/json",

            },

            body: JSON.stringify(payload),

        })

            .then(function (res) {

                if (!res.ok) {

                    var err = new Error("bad status");

                    err.status = res.status;

                    throw err;

                }

                return res.json().catch(function () {

                    return {};

                });

            })

            .then(function () {

                onDone(null, "success");

            })

            .catch(function () {

                onDone(

                    "We could not submit your request. Check your connection and try again.",

                    "error"

                );

            });

    }



    function wireBookingAnchors() {

        document.querySelectorAll('a[href="#booking"]').forEach(function (link) {

            if (link.closest("[data-open-modal]") || link.getAttribute("data-open-modal")) {

                return;

            }

            link.addEventListener("click", function (e) {

                var rt = link.getAttribute("data-request-type");

                if (rt && hubRequestType) {

                    hubRequestType.value = rt;

                } else if (link.classList.contains("pbj-audit-demo-cta__link") && hubRequestType) {

                    hubRequestType.value = "pilot_dashboard";

                }

                var booking = document.getElementById("booking");

                if (booking) {

                    e.preventDefault();

                    booking.scrollIntoView({ behavior: "smooth", block: "start" });

                    window.setTimeout(function () {

                        var focusEl = ccnInput || document.getElementById("hub-pro-email");

                        if (focusEl) {

                            try {

                                focusEl.focus({ preventScroll: true });

                            } catch (err) {

                                focusEl.focus();

                            }

                        }

                    }, 350);

                }

            });

        });

        var pilot = document.getElementById("pilot-dashboard-request");

        if (pilot) {

            pilot.addEventListener("click", function () {

                if (hubRequestType) hubRequestType.value = "pilot_dashboard";

            });

        }

    }



    wireBookingAnchors();



    function wireInquiryModal(cfg) {

        var form = document.getElementById(cfg.formId);

        if (!form) return;

        var statusNode = document.getElementById(cfg.statusId);

        var submitEl = document.getElementById(cfg.submitId);

        var successEl = document.getElementById(cfg.successId);

        var successEmailEl = document.getElementById(cfg.successEmailId);

        var honeypot = document.getElementById(cfg.honeypotId);

        var submitDefault = submitEl ? submitEl.innerHTML : "";



        function setModalStatus(message, tone) {

            if (!statusNode) return;

            statusNode.textContent = message || "";

            statusNode.classList.remove("pbj-hub-form-status--error", "pbj-hub-form-status--success");

            if (tone === "error") statusNode.classList.add("pbj-hub-form-status--error");

            if (tone === "success") statusNode.classList.add("pbj-hub-form-status--success");

        }



        form.addEventListener("submit", function (e) {

            e.preventDefault();

            form.classList.remove("was-validated");

            setModalStatus("", null);



            if (honeypot && strip(honeypot.value)) {

                return;

            }



            var emailVal = strip(document.getElementById(cfg.emailId).value);

            var emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailVal);

            var emailInput = document.getElementById(cfg.emailId);

            if (emailInput) {

                emailInput.setCustomValidity(emailOk ? "" : "invalid");

            }



            if (!form.checkValidity()) {

                form.classList.add("was-validated");

                return;

            }



            var nameVal = strip(document.getElementById(cfg.nameId).value);

            var payload = {

                request_type: cfg.requestType,

                name: nameVal,

                email: emailVal,

                source: "premium_hub",

            };



            if (cfg.requestType === "premium_inquiry" || cfg.requestType === "demo_request") {

                var ccnRaw = strip(document.getElementById(cfg.ccnId).value);

                var ccnResolved = resolveCcnFromInput(ccnRaw);

                payload.ccn = ccnResolved || null;

                payload.provider_name =

                    ccnResolved && LOOKUP[ccnResolved]

                        ? LOOKUP[ccnResolved].name

                        : ccnRaw || null;

                payload.notes = strip(document.getElementById(cfg.notesId).value) || null;

            } else {

                payload.facility_interest = strip(document.getElementById(cfg.scopeId).value);

                payload.notes = strip(document.getElementById(cfg.notesId).value);

            }



            if (submitEl) {

                submitEl.disabled = true;

                submitEl.innerHTML =

                    '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Sending…';

            }



            postPremiumRequest(payload, function (errMsg) {

                if (errMsg) {

                    setModalStatus(errMsg, "error");

                } else {

                    form.hidden = true;

                    if (successEl) {

                        successEl.hidden = false;

                        if (successEmailEl) successEmailEl.textContent = emailVal;

                    }

                    var lead = document.getElementById(cfg.leadId);

                    if (lead) lead.hidden = true;

                }

                if (submitEl) {

                    submitEl.disabled = false;

                    submitEl.innerHTML = submitDefault;

                }

            });

        });

    }



    wireInquiryModal({

        formId: "hub-premium-inquiry-form",

        statusId: "hub-premium-form-status",

        submitId: "hub-premium-submit",

        successId: "hub-premium-success",

        successEmailId: "hub-premium-success-email",

        honeypotId: "hub-premium-website",

        emailId: "hub-premium-email",

        nameId: "hub-premium-name",

        ccnId: "hub-premium-ccn",

        notesId: "hub-premium-notes",

        leadId: "modal-request-premium-lead",

        requestType: "premium_inquiry",

    });



    wireInquiryModal({

        formId: "hub-custom-work-form",

        statusId: "hub-custom-form-status",

        submitId: "hub-custom-submit",

        successId: "hub-custom-success",

        successEmailId: "hub-custom-success-email",

        honeypotId: "hub-custom-website",

        emailId: "hub-custom-email",

        nameId: "hub-custom-name",

        scopeId: "hub-custom-scope",

        notesId: "hub-custom-notes",

        leadId: "modal-custom-work-lead",

        requestType: "custom_work",

    });



    wireInquiryModal({

        formId: "hub-demo-request-form",

        statusId: "hub-demo-form-status",

        submitId: "hub-demo-submit",

        successId: "hub-demo-success",

        successEmailId: "hub-demo-success-email",

        honeypotId: "hub-demo-website",

        emailId: "hub-demo-email",

        nameId: "hub-demo-name",

        ccnId: "hub-demo-ccn",

        notesId: "hub-demo-notes",

        leadId: "modal-request-demo-lead",

        requestType: "demo_request",

    });



    function hideSuggest() {

        window.clearTimeout(blurTimer);

        if (suggestPanel) suggestPanel.hidden = true;

        if (ccnInput) ccnInput.setAttribute("aria-expanded", "false");

    }



    function renderSuggest(rows) {

        if (!suggestPanel || !suggestList || !ccnInput) return;

        suggestList.innerHTML = "";

        if (!rows || !rows.length) {

            hideSuggest();

            return;

        }

        for (var i = 0; i < rows.length; i++) {

            var row = rows[i];

            var li = document.createElement("li");

            li.setAttribute("role", "none");

            var btn = document.createElement("button");

            btn.type = "button";

            btn.className = "pbj-audit-ccn-suggest__item";

            btn.setAttribute("role", "option");

            btn.setAttribute("data-ccn", row.c);

            btn.innerHTML =

                '<span class="pbj-audit-ccn-suggest__ccn">' +

                escapeHtml(row.c) +

                '</span><span class="pbj-audit-ccn-suggest__name">' +

                escapeHtml(row.n) +

                "</span>";

            (function (ccn) {

                btn.addEventListener("click", function () {

                    ccnInput.value = ccn;

                    hideSuggest();

                });

            })(row.c);

            li.appendChild(btn);

            suggestList.appendChild(li);

        }

        suggestPanel.hidden = false;

        ccnInput.setAttribute("aria-expanded", "true");

    }



    function scheduleSuggest() {

        window.clearTimeout(suggestTimer);

        suggestTimer = window.setTimeout(function () {

            if (!PROVIDER_ROWS.length) {

                hideSuggest();

                return;

            }

            renderSuggest(filterRows(ccnInput.value));

        }, 100);

    }



    function wireUiOnce() {

        if (uiWired) return;

        uiWired = true;



        if (ccnInput) {

            ccnInput.addEventListener("input", scheduleSuggest);

            ccnInput.addEventListener("focus", function () {

                window.clearTimeout(blurTimer);

                scheduleSuggest();

            });

            ccnInput.addEventListener("keydown", function (e) {

                if (e.key === "Escape") hideSuggest();

            });

            ccnInput.addEventListener("blur", function () {

                var c = resolveCcnFromInput(ccnInput.value);

                if (/^[0-9]{6}$/.test(c)) {

                    ccnInput.value = c;

                }

                blurTimer = window.setTimeout(hideSuggest, 180);

            });

        }



        if (suggestPanel) {

            suggestPanel.addEventListener("mousedown", function (e) {

                e.preventDefault();

            });

        }



        if (sandboxForm) {

            sandboxForm.addEventListener("submit", function (e) {

                e.preventDefault();

                hideSuggest();

                sandboxForm.classList.remove("was-validated");

                setStatus("", null);



                if (!ccnInput || !hubEmail) return;



                if (hubWebsite && strip(hubWebsite.value)) {

                    return;

                }



                var bookingUrl = getBookingUrl();

                if (!bookingUrl) {

                    setStatus("Request service is not configured. Please try again later.", "error");

                    return;

                }



                var c = resolveCcnFromInput(ccnInput.value);

                if (!/^[0-9]{6}$/.test(c)) {

                    sandboxForm.classList.add("was-validated");

                    try {

                        ccnInput.focus();

                    } catch (err) {}

                    return;

                }

                ccnInput.value = c;



                var emailVal = strip(hubEmail.value);

                var emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailVal);

                if (!emailOk) {

                    hubEmail.setCustomValidity("invalid");

                } else {

                    hubEmail.setCustomValidity("");

                }



                if (!sandboxForm.checkValidity()) {

                    sandboxForm.classList.add("was-validated");

                    return;

                }



                var meta = getFacilityMeta(c);

                var rawCcn = strip(ccnInput.value);

                var providerName = meta ? meta.name : "";

                if (!providerName && rawCcn && normalizeCcn(rawCcn).length !== 6) {

                    providerName = rawCcn;

                }



                var auditFromVal = DEFAULT_AUDIT_FROM;

                var auditToVal = DEFAULT_AUDIT_TO;

                if (isDesktopDates() && auditFrom && auditTo) {

                    auditFromVal = strip(auditFrom.value) || DEFAULT_AUDIT_FROM;

                    auditToVal = strip(auditTo.value) || DEFAULT_AUDIT_TO;

                    if (!strip(auditFrom.value) || !strip(auditTo.value)) {

                        sandboxForm.classList.add("was-validated");

                        return;

                    }

                }



                var payload = {

                    request_type: hubRequestType ? strip(hubRequestType.value) || "pilot_dashboard" : "pilot_dashboard",

                    ccn: c,

                    provider_name: providerName || null,

                    audit_from: auditFromVal,

                    audit_to: auditToVal,

                    email: emailVal,

                    consult_times: hubConsultTimes ? strip(hubConsultTimes.value) || null : null,

                    care_compare_url:

                        meta && meta.careCompareHref ? meta.careCompareHref : careCompareUrlForCcn(c),

                    source: "premium_hub",

                };



                if (submitBtn) {

                    submitBtn.disabled = true;

                    submitBtn.classList.add("is-loading");

                    submitBtn.innerHTML =

                        '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Submitting…';

                }



                postPremiumRequest(payload, function (errMsg) {

                    if (errMsg) {

                        setStatus(errMsg, "error");

                    } else {

                        showSuccess(emailVal);

                    }

                    if (submitBtn) {

                        submitBtn.disabled = false;

                        submitBtn.classList.remove("is-loading");

                        submitBtn.innerHTML = submitBtnDefaultHtml;

                    }

                });

            });

        }

    }



    var fallbackRows = [{ c: "335513", n: "Seagate Rehabilitation and Nursing Center" }];



    fetch("/premium-assets/premium-nursing-homes.json", { credentials: "same-origin" })

        .then(function (r) {

            if (!r.ok) throw new Error("bad status");

            return r.json();

        })

        .then(function (rows) {

            if (!rows || !rows.length) throw new Error("empty");

            PROVIDER_ROWS = rows;

            buildIndexes(rows);

            wireUiOnce();

        })

        .catch(function () {

            PROVIDER_ROWS = fallbackRows;

            buildIndexes(fallbackRows);

            wireUiOnce();

        });

})();


