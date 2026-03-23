/**
 * Kitchen dashboard AJAX — intercepts "Взяти" and "Готово" forms
 * to avoid full page reload. Removes ticket card with animation,
 * updates badge counts, and removes empty order groups.
 */
(function () {
  "use strict";

  // Badge count selectors (desktop IDs + mobile pill badges)
  var BADGE_MAP = {
    pending: {
      desktop: "#pending-count",
      mobile: ".kitchen-tab-pills a[href='?tab=queue'] .badge",
    },
    taken: {
      desktop: "#taken-count",
      mobile: ".kitchen-tab-pills a[href='?tab=in_progress'] .badge",
    },
    done: {
      desktop: "#done-count",
      mobile: ".kitchen-tab-pills a[href='?tab=done'] .badge",
    },
  };

  function updateBadge(key, delta) {
    var sel = BADGE_MAP[key];
    if (!sel) return;

    // Desktop badge (always has ID)
    var desktopEl = document.querySelector(sel.desktop);
    if (desktopEl) {
      var dVal = Math.max(0, (parseInt(desktopEl.textContent, 10) || 0) + delta);
      desktopEl.textContent = dVal;
    }

    // Mobile pill badge — may need to be created
    var mobileEl = document.querySelector(sel.mobile);
    if (mobileEl) {
      var mVal = Math.max(0, (parseInt(mobileEl.textContent, 10) || 0) + delta);
      mobileEl.textContent = mVal;
      mobileEl.style.display = mVal === 0 ? "none" : "";
    } else if (delta > 0) {
      // Badge span doesn't exist — create it
      var linkSel = sel.mobile.replace(" .badge", "");
      var link = document.querySelector(linkSel);
      if (link) {
        var badge = document.createElement("span");
        var isActive = link.classList.contains("active");
        badge.className = "badge " + (isActive ? "bg-light text-primary" : "bg-primary") + " ms-1";
        badge.textContent = String(delta);
        link.appendChild(badge);
      }
    }
  }

  function removeTicketCard(ticketId) {
    var card = document.querySelector('[data-ticket-id="' + ticketId + '"]');
    if (!card) return;
    // Fade out
    card.style.transition = "opacity 0.3s, max-height 0.3s";
    card.style.opacity = "0";
    card.style.overflow = "hidden";
    setTimeout(function () {
      var group = card.closest(".kitchen-order-group");
      card.remove();
      // If order group is now empty, remove it
      if (group && group.querySelectorAll("[data-ticket-id]").length === 0) {
        group.remove();
      }
    }, 300);
  }

  // Intercept take/done form submissions
  document.addEventListener("submit", function (e) {
    var form = e.target.closest("form");
    if (!form) return;

    var action = form.getAttribute("action") || "";
    var isTake = action.indexOf("/ticket/") !== -1 && action.indexOf("/take/") !== -1;
    var isDone = action.indexOf("/ticket/") !== -1 && action.indexOf("/done/") !== -1;

    if (!isTake && !isDone) return;

    e.preventDefault();
    var btn = form.querySelector("button[type=submit]");
    if (btn) btn.disabled = true;

    console.log("[KitchenAjax] intercepted " + (isTake ? "take" : "done") + " url=" + action);

    var formData = new FormData(form);
    fetch(action, {
      method: "POST",
      headers: { "X-Requested-With": "XMLHttpRequest" },
      body: formData,
    })
      .then(function (resp) {
        return resp.json();
      })
      .then(function (data) {
        console.log("[KitchenAjax] response:", JSON.stringify(data));
        if (data.ok) {
          removeTicketCard(data.ticket_id);
          if (isTake) {
            updateBadge("pending", -1);
            updateBadge("taken", +1);
          } else if (isDone) {
            updateBadge("taken", -1);
            updateBadge("done", +1);
          }
        } else {
          console.warn("[KitchenAjax] error:", data.error);
          if (btn) btn.disabled = false;
        }
      })
      .catch(function (err) {
        console.error("[KitchenAjax] fetch failed:", err);
        if (btn) btn.disabled = false;
      });
  });

  // --- Urgency timer: update badges every 30s based on elapsed time ---
  var dashboard = document.getElementById("kitchen-dashboard");
  if (dashboard) {
    var warnMin = parseInt(dashboard.dataset.warnMin, 10) || 5;
    var criticalMin = parseInt(dashboard.dataset.criticalMin, 10) || 10;
    var _pageLoadedAt = Date.now();

    setInterval(function () {
      var elapsedMin = (Date.now() - _pageLoadedAt) / 60000;
      document.querySelectorAll("[data-ticket-id][data-age-min]").forEach(function (card) {
        var baseAge = parseInt(card.dataset.ageMin, 10) || 0;
        var currentAge = baseAge + elapsedMin;
        var currentUrgency = card.dataset.urgency || "normal";

        // Determine new urgency
        var newUrgency;
        if (currentAge >= criticalMin) newUrgency = "critical";
        else if (currentAge >= warnMin) newUrgency = "warn";
        else newUrgency = "normal";

        if (newUrgency === currentUrgency) return;

        // Update data attribute
        card.dataset.urgency = newUrgency;

        // Update CSS classes
        card.classList.remove("kitchen-urgency-critical", "kitchen-urgency-warn",
          "ticket-card-pending", "ticket-card-taken", "ticket-card-done");
        if (newUrgency === "critical") card.classList.add("kitchen-urgency-critical");
        else if (newUrgency === "warn") card.classList.add("kitchen-urgency-warn");

        // Update badge inside card
        var badges = card.querySelectorAll(".badge.bg-danger, .badge.bg-warning");
        badges.forEach(function (b) { b.remove(); });
        var infoDiv = card.querySelector(".flex-grow-1");
        if (infoDiv && newUrgency !== "normal") {
          var badge = document.createElement("span");
          badge.className = newUrgency === "critical"
            ? "badge bg-danger" : "badge bg-warning text-dark";
          badge.textContent = newUrgency === "critical" ? "Прострочено" : "Терміново!";
          infoDiv.querySelector("strong").after(badge);
        }

        // Update age text
        var ageEl = card.querySelector(".text-muted[style]");
        if (ageEl) {
          var txt = ageEl.textContent;
          ageEl.textContent = txt.replace(/^\d+ хв/, Math.round(currentAge) + " хв");
        }
      });
    }, 30000);
  }
})();
