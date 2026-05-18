/**
 * Premium hub modals — Bootstrap-compatible markup, no Tailwind.
 */
(function () {
    /** Reserved for optional linked evidence modals (gallery prev/next). */
    var FORENSIC_GALLERY_IDS = [];

    function modalEl(id) {
        return document.getElementById("modal-" + id);
    }

    function isOpen(m) {
        return m && m.classList.contains("is-open");
    }

    var lastFocus = null;

    function resetInquiryModal(id) {
        if (id !== "request-premium" && id !== "custom-work" && id !== "request-demo") return;
        var formId =
            id === "request-premium"
                ? "hub-premium-inquiry-form"
                : id === "request-demo"
                  ? "hub-demo-request-form"
                  : "hub-custom-work-form";
        var successId =
            id === "request-premium"
                ? "hub-premium-success"
                : id === "request-demo"
                  ? "hub-demo-success"
                  : "hub-custom-success";
        var leadId =
            id === "request-premium"
                ? "modal-request-premium-lead"
                : id === "request-demo"
                  ? "modal-request-demo-lead"
                  : "modal-custom-work-lead";
        var statusId =
            id === "request-premium"
                ? "hub-premium-form-status"
                : id === "request-demo"
                  ? "hub-demo-form-status"
                  : "hub-custom-form-status";
        var form = document.getElementById(formId);
        var success = document.getElementById(successId);
        var lead = document.getElementById(leadId);
        var status = document.getElementById(statusId);
        if (form) {
            form.hidden = false;
            form.reset();
            form.classList.remove("was-validated");
        }
        if (success) success.hidden = true;
        if (lead) lead.hidden = false;
        if (status) status.textContent = "";
    }

    function openModal(id, options) {
        options = options || {};
        if (!options.skipStoreLastFocus) {
            lastFocus = document.activeElement;
        }
        var m = modalEl(id);
        if (!m) return;
        resetInquiryModal(id);
        m.classList.add("is-open");
        m.setAttribute("aria-hidden", "false");
        document.body.style.overflow = "hidden";
        var btn = m.querySelector("[data-modal-close]");
        if (btn) btn.focus();
    }

    function closeModal(m, opts) {
        opts = opts || {};
        if (!m) return;
        m.classList.remove("is-open");
        m.setAttribute("aria-hidden", "true");
        document.body.style.overflow = "";
        if (!opts.skipFocusRestore && lastFocus && typeof lastFocus.focus === "function") {
            try {
                lastFocus.focus();
            } catch (e) {}
        }
    }

    function currentForensicModalId() {
        for (var i = 0; i < FORENSIC_GALLERY_IDS.length; i++) {
            var id = FORENSIC_GALLERY_IDS[i];
            var m = modalEl(id);
            if (m && m.classList.contains("is-open")) return id;
        }
        return null;
    }

    function stepGallery(delta) {
        var cur = currentForensicModalId();
        if (!cur) return;
        var idx = FORENSIC_GALLERY_IDS.indexOf(cur);
        if (idx < 0) return;
        var n = FORENSIC_GALLERY_IDS.length;
        var nextIdx = (idx + delta + n) % n;
        var nextId = FORENSIC_GALLERY_IDS[nextIdx];
        var curM = modalEl(cur);
        closeModal(curM, { skipFocusRestore: true });
        openModal(nextId, { skipStoreLastFocus: true });
    }

    document.addEventListener("click", function (e) {
        var t = e.target;
        if (!(t instanceof Element)) return;

        var gal = t.closest("[data-modal-gallery]");
        if (gal) {
            e.preventDefault();
            var dir = gal.getAttribute("data-modal-gallery");
            if (dir === "next") stepGallery(1);
            else if (dir === "prev") stepGallery(-1);
            return;
        }

        var op = t.closest("[data-open-modal]");
        if (op) {
            e.preventDefault();
            openModal(op.getAttribute("data-open-modal"));
            return;
        }
        if (t.getAttribute("data-modal-backdrop") === "true") {
            var m = t.closest(".pbj-hub-modal");
            if (m) closeModal(m);
            return;
        }
        if (t.closest("[data-modal-close]")) {
            var modal = t.closest(".pbj-hub-modal");
            if (modal) closeModal(modal);
        }
    });

    document.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
            var active = document.activeElement;
            if (
                active &&
                active.classList &&
                active.classList.contains("pbj-hub-feature-card--clickable")
            ) {
                e.preventDefault();
                var mid = active.getAttribute("data-open-modal");
                if (mid) openModal(mid);
                return;
            }
        }
        if (e.key !== "Escape") return;
        document.querySelectorAll(".pbj-hub-modal.is-open").forEach(function (m) {
            e.preventDefault();
            closeModal(m);
        });
    });

    /** Hub sandbox / mailto flows call this after modals.js loads. */
    window.pbjHubOpenModal = function (id) {
        openModal(id);
    };

    function initFeaturesCarousel() {
        var track = document.getElementById("audit-features-track");
        var dotsWrap = document.getElementById("audit-features-dots");
        if (!track || !dotsWrap) return;

        var slides = track.querySelectorAll(".pbj-audit-features__slide");
        var dots = dotsWrap.querySelectorAll(".pbj-audit-features__dot");
        if (!slides.length) return;

        var index = 0;
        var timer = null;
        var pauseUntil = 0;

        function syncSlideWidths() {
            var w = track.clientWidth;
            if (!w) return;
            slides.forEach(function (slide) {
                slide.style.flexBasis = w + "px";
                slide.style.width = w + "px";
                slide.style.maxWidth = w + "px";
                slide.style.minWidth = w + "px";
            });
        }

        function scrollToIndex(i, behavior) {
            syncSlideWidths();
            index = ((i % slides.length) + slides.length) % slides.length;
            var slide = slides[index];
            if (!slide) return;
            track.scrollTo({ left: slide.offsetLeft, behavior: behavior || "smooth" });
            dots.forEach(function (dot, di) {
                var on = di === index;
                dot.classList.toggle("is-active", on);
                dot.setAttribute("aria-selected", on ? "true" : "false");
            });
        }

        function scheduleAuto() {
            if (timer) window.clearInterval(timer);
            timer = window.setInterval(function () {
                if (Date.now() < pauseUntil) return;
                scrollToIndex(index + 1, "smooth");
            }, 5500);
        }

        dots.forEach(function (dot) {
            dot.addEventListener("click", function () {
                var n = parseInt(dot.getAttribute("data-slide"), 10);
                if (!isNaN(n)) {
                    pauseUntil = Date.now() + 8000;
                    scrollToIndex(n, "smooth");
                }
            });
        });

        track.addEventListener("scroll", function () {
            var center = track.scrollLeft + track.clientWidth / 2;
            var best = index;
            var bestDist = Infinity;
            slides.forEach(function (slide, si) {
                var mid = slide.offsetLeft + slide.offsetWidth / 2;
                var dist = Math.abs(mid - center);
                if (dist < bestDist) {
                    bestDist = dist;
                    best = si;
                }
            });
            if (best !== index) {
                index = best;
                dots.forEach(function (dot, di) {
                    var on = di === index;
                    dot.classList.toggle("is-active", on);
                    dot.setAttribute("aria-selected", on ? "true" : "false");
                });
            }
        }, { passive: true });

        track.addEventListener("touchstart", function () {
            pauseUntil = Date.now() + 8000;
        }, { passive: true });

        syncSlideWidths();
        scrollToIndex(0, "auto");
        scheduleAuto();
        window.addEventListener("resize", function () {
            syncSlideWidths();
            scrollToIndex(index, "auto");
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initFeaturesCarousel);
    } else {
        initFeaturesCarousel();
    }
})();
