/**
 * Waiter SSE handlers — AJAX partial DOM updates instead of full reload.
 * Registers page-specific handlers via window.SSE_HANDLERS registry.
 * Requires sse_client.js to be loaded first (provides SSE_UTILS).
 */
(function () {
  "use strict";

  var u = window.SSE_UTILS;
  if (!u) return; // sse_client.js not loaded

  var _pendingRefresh = {}; // orderId -> debounce timeout

  // --- Self-skip: ignore events triggered by current user ---
  function isSelfTriggered(data) {
    return (
      data.actor_id &&
      window.SSE_CURRENT_USER_ID &&
      data.actor_id === window.SSE_CURRENT_USER_ID
    );
  }

  // --- Core: refresh a single accordion item via AJAX partial ---
  function refreshAccordionItem(orderId) {
    if (_pendingRefresh[orderId]) clearTimeout(_pendingRefresh[orderId]);
    _pendingRefresh[orderId] = setTimeout(function () {
      delete _pendingRefresh[orderId];
      _doRefreshAccordionItem(orderId);
    }, 300);
  }

  function _doRefreshAccordionItem(orderId) {
    var item = document.querySelector(
      '.accordion-item[data-order-id="' + orderId + '"]'
    );
    if (!item) return;

    var parent = item.closest(".accordion");
    var parentId = parent ? parent.id : "accMyOrders";
    var idPrefix = parentId === "accMyOrders" ? "my" : "tw";

    // Remember open state
    var collapse = item.querySelector(".accordion-collapse");
    var wasOpen = collapse && collapse.classList.contains("show");

    var url =
      "/waiter/order/" +
      orderId +
      "/partial/accordion/?id_prefix=" +
      idPrefix +
      "&parent_id=" +
      parentId;

    fetch(url)
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.text();
      })
      .then(function (html) {
        var temp = document.createElement("div");
        temp.innerHTML = html.trim();
        var newItem = temp.firstElementChild;
        if (!newItem) return;

        // Preserve accordion open state
        if (wasOpen) {
          var newCollapse = newItem.querySelector(".accordion-collapse");
          if (newCollapse) {
            newCollapse.classList.add("show");
            var newButton = newItem.querySelector(".accordion-button");
            if (newButton) newButton.classList.remove("collapsed");
          }
        }

        item.replaceWith(newItem);
        console.log("[WaiterSSE] accordion refreshed order=" + orderId);
      })
      .catch(function (err) {
        console.warn("[WaiterSSE] accordion partial failed, reload", err);
        location.reload();
      });
  }

  // --- Core: refresh detail card via AJAX partial ---
  function refreshDetailCard(orderId) {
    var detailEl = document.querySelector(
      '#order-detail-card[data-order-id="' + orderId + '"]'
    );
    if (!detailEl) return;

    fetch("/waiter/order/" + orderId + "/partial/detail/")
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.text();
      })
      .then(function (html) {
        detailEl.innerHTML = html;
        console.log("[WaiterSSE] detail refreshed order=" + orderId);
      })
      .catch(function (err) {
        console.warn("[WaiterSSE] detail partial failed, reload", err);
        location.reload();
      });
  }

  // --- Core: remove accordion item with fade ---
  function removeAccordionItem(orderId) {
    var item = document.querySelector(
      '.accordion-item[data-order-id="' + orderId + '"]'
    );
    if (!item) return;
    item.style.transition = "opacity 0.3s";
    item.style.opacity = "0";
    setTimeout(function () {
      item.remove();
    }, 300);
  }

  // --- Core: update badge count via poll endpoint ---
  function updateBadgeCounts() {
    fetch("/waiter/poll/")
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        _setBadge("new", data.new_count);
        _setBadge("my", data.my_count);
      })
      .catch(function () {});
  }

  function _setBadge(key, count) {
    var el = document.querySelector('[data-poll-count="' + key + '"]');
    if (!el) return;
    el.textContent = count;
    if (count > 0) {
      el.classList.remove("d-none");
    } else {
      el.classList.add("d-none");
    }
  }

  // =====================================================================
  // SSE Handler Registration
  // =====================================================================

  window.SSE_HANDLERS = window.SSE_HANDLERS || {};

  window.SSE_HANDLERS["order_accepted"] = function (data) {
    console.log("[WaiterSSE] order_accepted order=" + data.order_id + " waiter=" + data.waiter_id);
    if (data.waiter_id && data.waiter_id === window.SSE_CURRENT_USER_ID) {
      console.log("[WaiterSSE] self-triggered accept, skip");
      return;
    }
    // Remove from "Нові" tab
    var newItem = document.querySelector(
      '#new-orders-list [data-order-id="' + data.order_id + '"]'
    );
    if (newItem) {
      newItem.style.transition = "opacity 0.3s";
      newItem.style.opacity = "0";
      setTimeout(function () { newItem.remove(); }, 300);
    }
    var modal = document.getElementById("newOrderModal" + data.order_id);
    if (modal) modal.remove();
    updateBadgeCounts();
  };

  window.SSE_HANDLERS["order_submitted"] = function (data) {
    console.log("[WaiterSSE] order_submitted order=" + data.order_id);
    u.showFlash(
      "Нове замовлення #" + data.order_id + " від клієнта",
      "info"
    );
    u.sseBeep(660, 0.2);
    u.updateNavBadge("nav-badge-orders", u.BADGE_ORDERS_KEY, 1);
    updateBadgeCounts();
    // If on "Нові" tab, reload just that tab content
    var newList = document.getElementById("new-orders-list");
    if (newList) {
      u.scheduleReload(2000); // "Нові" tab — simple reload is fine
    }
  };

  window.SSE_HANDLERS["ticket_done"] = function (data) {
    console.log(
      "[WaiterSSE] ticket_done ticket=" +
        data.ticket_id +
        " order=" +
        data.order_id
    );
    u.showFlash(
      "Страва готова: " + (data.dish || "#" + data.ticket_id),
      "success"
    );
    u.updateNavBadge("nav-badge-orders", u.BADGE_ORDERS_KEY, 1);
    refreshAccordionItem(data.order_id);
    refreshDetailCard(data.order_id);
  };

  window.SSE_HANDLERS["ticket_taken"] = function (data) {
    console.log(
      "[WaiterSSE] ticket_taken ticket=" +
        data.ticket_id +
        " order=" +
        data.order_id
    );
    refreshAccordionItem(data.order_id);
    refreshDetailCard(data.order_id);
  };

  window.SSE_HANDLERS["order_ready"] = function (data) {
    console.log("[WaiterSSE] order_ready order=" + data.order_id);
    u.showFlash("Замовлення #" + data.order_id + " готове!", "success");
    u.updateNavBadge("nav-badge-orders", u.BADGE_ORDERS_KEY, 1);
    refreshAccordionItem(data.order_id);
    refreshDetailCard(data.order_id);
  };

  window.SSE_HANDLERS["order_updated"] = function (data) {
    console.log("[WaiterSSE] order_updated order=" + data.order_id);
    if (isSelfTriggered(data)) {
      console.log("[WaiterSSE] self-triggered, skip");
      return;
    }
    refreshAccordionItem(data.order_id);
    refreshDetailCard(data.order_id);
  };

  window.SSE_HANDLERS["order_cancelled"] = function (data) {
    console.log("[WaiterSSE] order_cancelled order=" + data.order_id);
    if (isSelfTriggered(data)) {
      console.log("[WaiterSSE] self-triggered, skip");
      return;
    }
    u.showFlash("Замовлення #" + data.order_id + " скасовано", "warning");
    removeAccordionItem(data.order_id);
    // Remove from "Нові" tab if present
    var newItem = document.querySelector(
      '#new-orders-list [data-order-id="' + data.order_id + '"]'
    );
    if (newItem) newItem.remove();
    var modal = document.getElementById("newOrderModal" + data.order_id);
    if (modal) modal.remove();
    updateBadgeCounts();
  };
})();
