/**
 * Offline mode detector.
 * Shows banner and disables forms when network is lost.
 * Restores UI when connection returns.
 */
(function () {
    "use strict";

    const BANNER_ID = "offline-banner";

    function showOfflineBanner() {
        console.warn("[Offline] network LOST — showing offline banner");
        if (document.getElementById(BANNER_ID)) return;

        const banner = document.createElement("div");
        banner.id = BANNER_ID;
        banner.className = "alert alert-warning text-center mb-0 rounded-0";
        banner.setAttribute("role", "alert");
        banner.style.position = "sticky";
        banner.style.top = "0";
        banner.style.zIndex = "1050";
        banner.textContent =
            "\u{1F4F5} " + gettext("Офлайн-режим \u2014 меню може бути застарілим. Замовлення недоступні.");
        document.body.prepend(banner);

        document.querySelectorAll(".form-needs-network").forEach((form) => {
            form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(
                (btn) => {
                    btn.disabled = true;
                },
            );
        });
    }

    function hideOfflineBanner() {
        console.log("[Offline] network RESTORED — hiding offline banner");
        const banner = document.getElementById(BANNER_ID);
        if (banner) banner.remove();

        document.querySelectorAll(".form-needs-network").forEach((form) => {
            form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(
                (btn) => {
                    btn.disabled = false;
                },
            );
        });
    }

    window.addEventListener("online", () => hideOfflineBanner());
    window.addEventListener("offline", () => showOfflineBanner());

    if (!navigator.onLine) {
        document.addEventListener("DOMContentLoaded", showOfflineBanner);
    }
})();
