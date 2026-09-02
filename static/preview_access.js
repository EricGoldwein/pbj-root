/** Minimal CTA helper for central Superdynamic preview — no dashboard boot. */
(function () {
    'use strict';
    window.pbjPreviewOpenAccessCta = function (event) {
        if (event && typeof event.preventDefault === 'function') {
            event.preventDefault();
        }
        var href = document.body && document.body.getAttribute('data-pbj-preview-cta-href');
        if (href) {
            window.location.href = href;
        }
        return false;
    };
})();
