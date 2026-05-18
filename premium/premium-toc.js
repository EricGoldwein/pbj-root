/**
 * Sticky “On this page” pills + mobile read-progress bar.
 * Document Y via getBoundingClientRect (nested sections). After a pill click or hash jump,
 * briefly ignores scroll-based sync so the browser’s delayed scroll doesn’t clear .is-active.
 */
(function () {
    var bar = document.querySelector(".pbj-premium-toc-bar");
    var list = document.querySelector(".pbj-premium-toc-pills");
    if (!bar || !list) return;

    var links = Array.prototype.slice.call(list.querySelectorAll('a[href^="#"]'));
    if (!links.length) return;

    function elementDocumentTop(el) {
        return el.getBoundingClientRect().top + (window.scrollY || document.documentElement.scrollTop);
    }

    var pairs = links
        .map(function (a) {
            var id = a.getAttribute("href").slice(1);
            var sec = id ? document.getElementById(id) : null;
            return sec ? { a: a, el: sec } : null;
        })
        .filter(Boolean);

    if (!pairs.length) return;

    pairs.sort(function (x, y) {
        return elementDocumentTop(x.el) - elementDocumentTop(y.el);
    });

    var progressBar = bar.querySelector(".pbj-premium-toc-progress-bar");
    /** While Date.now() < this, scroll handler must not overwrite pill state (click/hash in flight). */
    var ignoreScrollUntil = 0;

    function stickyOffset() {
        var nav = document.querySelector(".pbj-premium-nav-wrap");
        var navH = nav ? nav.offsetHeight : 56;
        var tocH = bar.offsetHeight || 48;
        return navH + tocH + 8;
    }

    function applyPillsForSectionId(sectionId) {
        pairs.forEach(function (p) {
            var on = p.el.id === sectionId;
            p.a.classList.toggle("is-active", on);
            if (on) {
                p.a.setAttribute("aria-current", "true");
            } else {
                p.a.removeAttribute("aria-current");
            }
        });
    }

    function updateReadProgress() {
        if (!progressBar) return;
        if (window.matchMedia("(min-width: 768px)").matches) {
            progressBar.style.width = "0%";
            return;
        }
        var docEl = document.documentElement;
        var y = window.scrollY || docEl.scrollTop;
        var scrollable = docEl.scrollHeight - window.innerHeight;
        var pct =
            scrollable <= 0 ? 0 : Math.min(100, Math.max(0, (y / scrollable) * 100));
        progressBar.style.width = pct + "%";
    }

    function syncPillsFromScroll() {
        if (Date.now() < ignoreScrollUntil) {
            updateReadProgress();
            return;
        }
        var y = window.scrollY || document.documentElement.scrollTop;
        var probeY = y + stickyOffset() + 4;
        var current = pairs[0].el;
        for (var i = 0; i < pairs.length; i++) {
            if (elementDocumentTop(pairs[i].el) <= probeY) {
                current = pairs[i].el;
            }
        }
        applyPillsForSectionId(current.id);
        updateReadProgress();
    }

    function armIgnoreFromUserNav(ms) {
        ignoreScrollUntil = Date.now() + (ms || 700);
    }

    pairs.forEach(function (p) {
        p.a.addEventListener(
            "click",
            function () {
                var id = p.a.getAttribute("href").slice(1);
                armIgnoreFromUserNav(850);
                applyPillsForSectionId(id);
                window.requestAnimationFrame(function () {
                    updateReadProgress();
                });
            },
            false
        );
    });

    window.addEventListener("scroll", syncPillsFromScroll, { passive: true });
    window.addEventListener("resize", syncPillsFromScroll, { passive: true });

    window.addEventListener("hashchange", function () {
        var hid = (location.hash || "").replace(/^#/, "");
        if (!hid || !document.getElementById(hid)) return;
        armIgnoreFromUserNav(600);
        applyPillsForSectionId(hid);
        updateReadProgress();
    });

    function initialHash() {
        var hid = (location.hash || "").replace(/^#/, "");
        if (!hid || !document.getElementById(hid)) return;
        armIgnoreFromUserNav(400);
        applyPillsForSectionId(hid);
    }

    initialHash();
    syncPillsFromScroll();
})();
