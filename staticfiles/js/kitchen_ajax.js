/**
 * Kitchen dashboard AJAX — intercepts "Взяти" and "Готово" forms
 * to avoid full page reload. Moves ticket card between kanban columns
 * with animation, updates badge counts, and removes empty order groups.
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

  // Desktop kanban column body selectors
  var KANBAN_COL = {
    pending: ".kitchen-kanban .kanban-col:nth-child(1) .card-body",
    taken: ".kitchen-kanban .kanban-col:nth-child(2) .card-body",
    done: ".kitchen-kanban .kanban-col:nth-child(3) .card-body",
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

  /** Check if we are in desktop kanban layout. */
  function isKanban() {
    return !!document.querySelector(".kitchen-kanban");
  }

  /** Remove the "empty" placeholder from a column body if present. */
  function removeEmptyPlaceholder(colBody) {
    var ph = colBody.querySelector(".text-muted.text-center");
    if (ph) ph.remove();
  }

  /** If column body has no ticket cards left, add an empty placeholder. */
  function addEmptyPlaceholderIfNeeded(colBody, text) {
    if (colBody.querySelectorAll("[data-ticket-id]").length === 0) {
      var div = document.createElement("div");
      div.className = "text-muted text-center py-4";
      div.innerHTML = '<i class="bi bi-inbox"></i> ' + text;
      colBody.appendChild(div);
    }
  }

  /**
   * Find or create an order group in the target column for the given order.
   * Returns the .list-group element inside the group.
   */
  function getOrCreateOrderGroup(colBody, orderId, waiterLabel) {
    // Look for existing group by matching order id in header text
    var groups = colBody.querySelectorAll(".kitchen-order-group");
    for (var i = 0; i < groups.length; i++) {
      var header = groups[i].querySelector(".kitchen-order-group-header");
      if (header && header.textContent.indexOf("#" + orderId) !== -1) {
        return groups[i].querySelector(".list-group");
      }
    }
    // Create new group
    var group = document.createElement("div");
    group.className = "kitchen-order-group";
    group.innerHTML =
      '<div class="kitchen-order-group-header d-flex justify-content-between align-items-center">' +
        '<span>#' + orderId + ' \u00B7 ' + waiterLabel + '</span>' +
        '<span class="badge bg-secondary">0 ' + gettext("стр.") + '</span>' +
      '</div>' +
      '<div class="list-group list-group-flush"></div>';
    colBody.appendChild(group);
    return group.querySelector(".list-group");
  }

  /** Update the ticket count badge inside an order group header. */
  function updateGroupCount(group) {
    if (!group) return;
    var orderGroup = group.closest(".kitchen-order-group");
    if (!orderGroup) return;
    var count = orderGroup.querySelectorAll("[data-ticket-id]").length;
    var badge = orderGroup.querySelector(".kitchen-order-group-header .badge");
    if (badge) {
      badge.textContent = count + " " + gettext("стр.");
    }
  }

  /**
   * Rebuild the action button inside a ticket card for the new column.
   * "take" → "done", "done" → "handoff"
   */
  function rebuildButton(card, ticketId, newAction) {
    var btnWrap = card.querySelector(".flex-shrink-0");
    if (!btnWrap) return;

    if (newAction === "done") {
      btnWrap.innerHTML =
        '<form method="post" action="/kitchen/ticket/' + ticketId + '/done/">' +
          '<input type="hidden" name="csrfmiddlewaretoken" value="' + getCSRF() + '">' +
          '<input type="hidden" name="tab" value="in_progress">' +
          '<button type="submit" class="btn btn-success btn-sm" style="min-height: 44px; min-width: 70px;">' +
            '<i class="bi bi-check-lg"></i> ' + gettext("Готово") +
          '</button>' +
        '</form>';
    } else if (newAction === "handoff") {
      btnWrap.innerHTML =
        '<div class="d-flex gap-1">' +
          '<a href="/kitchen/ticket/' + ticketId + '/handoff/" class="btn btn-outline-primary btn-sm" style="min-height: 44px;">' +
            '<i class="bi bi-qr-code"></i>' +
          '</a>' +
          '<form method="post" action="/kitchen/ticket/' + ticketId + '/manual-handoff/" class="d-inline ajax-deliver">' +
            '<input type="hidden" name="csrfmiddlewaretoken" value="' + getCSRF() + '">' +
            '<input type="hidden" name="tab" value="done">' +
            '<button type="submit" class="btn btn-outline-secondary btn-sm" style="min-height: 44px;">' +
              '<i class="bi bi-hand-index"></i>' +
            '</button>' +
          '</form>' +
        '</div>';
    }
  }

  function getCSRF() {
    var el = document.querySelector("[name=csrfmiddlewaretoken]");
    return el ? el.value : "";
  }

  /**
   * Extract order id and waiter label from the ticket card's text.
   */
  function getOrderInfo(card) {
    var meta = card.querySelector(".text-muted[style]");
    var text = meta ? meta.textContent : "";
    // Format: "#123 · Офіціант Дмитро"
    var m = text.match(/#(\d+)\s*·\s*(.*)/);
    return {
      orderId: m ? m[1] : "?",
      waiterLabel: m ? m[2].trim() : "",
    };
  }

  /**
   * Move a ticket card from source column to target column with animation.
   * Mobile: just remove (single tab view). Desktop kanban: move between columns.
   */
  function moveTicketCard(ticketId, sourceKey, targetKey) {
    var card = document.querySelector('[data-ticket-id="' + ticketId + '"]');
    if (!card) return;

    var sourceGroup = card.closest(".kitchen-order-group");
    var sourceList = card.closest(".list-group");

    if (isKanban()) {
      var targetColBody = document.querySelector(KANBAN_COL[targetKey]);
      if (!targetColBody) { removeCardMobile(card, sourceGroup); return; }

      var info = getOrderInfo(card);
      var targetList = getOrCreateOrderGroup(targetColBody, info.orderId, info.waiterLabel);

      // Reset card styling
      card.classList.remove("kitchen-urgency-critical", "kitchen-urgency-warn",
        "ticket-card-pending", "ticket-card-taken", "ticket-card-done");
      card.classList.add("ticket-card-" + (targetKey === "taken" ? "taken" : "done"));
      card.dataset.urgency = "normal";

      // Rebuild button for new column
      var newAction = targetKey === "taken" ? "done" : "handoff";
      rebuildButton(card, ticketId, newAction);

      // Fade out from source
      card.style.transition = "opacity 0.25s";
      card.style.opacity = "0";

      setTimeout(function () {
        // Move to target
        card.remove();
        cleanupSourceGroup(sourceGroup, sourceList, sourceKey);

        removeEmptyPlaceholder(targetColBody);
        targetList.appendChild(card);
        updateGroupCount(targetList);

        // Fade in
        requestAnimationFrame(function () {
          card.style.opacity = "0";
          requestAnimationFrame(function () {
            card.style.transition = "opacity 0.3s";
            card.style.opacity = "1";
          });
        });
      }, 250);
    } else {
      // Mobile: just fade out and remove
      removeCardMobile(card, sourceGroup);
    }
  }

  function removeCardMobile(card, group) {
    card.style.transition = "opacity 0.3s, max-height 0.3s";
    card.style.opacity = "0";
    card.style.overflow = "hidden";
    setTimeout(function () {
      card.remove();
      if (group && group.querySelectorAll("[data-ticket-id]").length === 0) {
        group.remove();
      }
    }, 300);
  }

  function cleanupSourceGroup(group, list, sourceKey) {
    if (!group) return;
    updateGroupCount(list);
    if (group.querySelectorAll("[data-ticket-id]").length === 0) {
      group.remove();
    }
    // Add placeholder if column is now empty
    var colBody = document.querySelector(KANBAN_COL[sourceKey]);
    if (colBody) {
      var emptyTexts = { pending: gettext("Черга порожня"), taken: gettext("Нічого в роботі"), done: gettext("Ще нічого не приготовлено") };
      addEmptyPlaceholderIfNeeded(colBody, emptyTexts[sourceKey] || "");
    }
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
          if (isTake) {
            moveTicketCard(data.ticket_id, "pending", "taken");
            updateBadge("pending", -1);
            updateBadge("taken", +1);
          } else if (isDone) {
            moveTicketCard(data.ticket_id, "taken", "done");
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
          badge.textContent = newUrgency === "critical" ? gettext("Прострочено") : gettext("Терміново!");
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
