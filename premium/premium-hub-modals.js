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

    function openModal(id, options) {
        options = options || {};
        if (!options.skipStoreLastFocus) {
            lastFocus = document.activeElement;
        }
        var m = modalEl(id);
        if (!m) return;
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
})();
