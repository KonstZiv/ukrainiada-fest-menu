/**
 * Offline mode detector.
 * Shows banner and disables forms when network is lost.
 * Restores UI when connection returns.
 */
(function () {
    "use strict";

    var BANNER_ID = "offline-banner";

    function showOfflineBanner() {
        if (document.getElementById(BANNER_ID)) return;

        var banner = document.createElement("div");
        banner.id = BANNER_ID;
        banner.className = "alert alert-warning text-center mb-0 rounded-0";
        banner.setAttribute("role", "alert");
        banner.style.position = "sticky";
        banner.style.top = "0";
        banner.style.zIndex = "1050";
        banner.textContent =
            "\u{1F4F5} \u041E\u0444\u043B\u0430\u0439\u043D-\u0440\u0435\u0436\u0438\u043C \u2014 \u043C\u0435\u043D\u044E \u043C\u043E\u0436\u0435 \u0431\u0443\u0442\u0438 \u0437\u0430\u0441\u0442\u0430\u0440\u0456\u043B\u0438\u043C. \u0417\u0430\u043C\u043E\u0432\u043B\u0435\u043D\u043D\u044F \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u043D\u0456.";
        document.body.prepend(banner);

        // Disable forms that need network
        document.querySelectorAll(".form-needs-network").forEach(function (form) {
            form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(
                function (btn) {
                    btn.disabled = true;
                },
            );
        });
    }

    function hideOfflineBanner() {
        var banner = document.getElementById(BANNER_ID);
        if (banner) banner.remove();

        document.querySelectorAll(".form-needs-network").forEach(function (form) {
            form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(
                function (btn) {
                    btn.disabled = false;
                },
            );
        });
    }

    window.addEventListener("online", function () {
        hideOfflineBanner();
    });

    window.addEventListener("offline", function () {
        showOfflineBanner();
    });

    if (!navigator.onLine) {
        document.addEventListener("DOMContentLoaded", showOfflineBanner);
    }
})();
