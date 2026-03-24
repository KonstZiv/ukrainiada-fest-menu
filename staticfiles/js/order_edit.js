/**
 * Order editing — [−][qty][+] buttons for item quantity changes.
 * Sends AJAX POST, updates DOM inline. Debounces rapid clicks (300ms).
 * Shared between visitor order_detail and waiter waiter_order_detail.
 */
(function () {
  "use strict";

  var config = document.getElementById("order-edit-config");
  if (!config) return;

  var editUrl = config.dataset.editUrl;
  var cancelUrl = config.dataset.cancelUrl;
  var csrfToken = config.dataset.csrf;
  var pendingChanges = {};
  var debounceTimer = null;

  function formatPrice(val) {
    return "\u20ac" + parseFloat(val).toFixed(2);
  }

  // --- Quantity button clicks ---
  document.addEventListener("click", function (e) {
    var btn = e.target.closest(".order-qty-btn");
    if (!btn) return;

    var itemId = btn.dataset.itemId;
    var action = btn.dataset.action;
    var qtyEl = document.querySelector(
      '.order-item-qty[data-item-id="' + itemId + '"]'
    );
    if (!qtyEl) return;

    var current = parseInt(qtyEl.textContent, 10);
    var newQty = action === "increase" ? current + 1 : Math.max(0, current - 1);
    qtyEl.textContent = newQty;
    pendingChanges[itemId] = newQty;

    // Optimistic subtotal update
    var row = document.querySelector(
      '[data-order-item-id="' + itemId + '"]'
    );
    if (row) {
      var price = parseFloat(row.dataset.dishPrice);
      var subtotalEl = row.querySelector(".order-item-subtotal");
      if (subtotalEl) {
        subtotalEl.textContent = newQty > 0 ? formatPrice(price * newQty) : formatPrice(0);
      }
      // Fade out zero-qty row
      row.style.opacity = newQty === 0 ? "0.4" : "1";
    }

    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(flushChanges, 300);
  });

  function flushChanges() {
    if (Object.keys(pendingChanges).length === 0) return;
    var changes = {};
    for (var k in pendingChanges) {
      changes[k] = pendingChanges[k];
    }
    pendingChanges = {};

    console.log("[OrderEdit] flush", changes);

    fetch(editUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
        "X-Requested-With": "XMLHttpRequest",
      },
      body: JSON.stringify({ items: changes }),
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        console.log("[OrderEdit] response", data);
        if (!data.ok) {
          console.error("[OrderEdit] error:", data.error);
          location.reload();
          return;
        }
        if (data.status === "cancelled") {
          showCancelledState();
          return;
        }
        // Update total
        var totalEl = document.querySelector(".order-total-value");
        if (totalEl) {
          totalEl.innerHTML =
            totalEl.textContent.split("\u20ac")[0] + formatPrice(data.total_price);
        }
        // Remove zero-qty items from DOM
        var existingIds = data.items.map(function (i) {
          return String(i.id);
        });
        document
          .querySelectorAll("[data-order-item-id]")
          .forEach(function (row) {
            if (existingIds.indexOf(row.dataset.orderItemId) === -1) {
              row.remove();
            }
          });
      })
      .catch(function (err) {
        console.error("[OrderEdit]", err);
      });
  }

  // --- Cancel button ---
  var cancelBtn = document.getElementById("order-cancel-btn");
  if (cancelBtn) {
    cancelBtn.addEventListener("click", function () {
      if (!confirm("Скасувати замовлення?")) return;

      cancelBtn.disabled = true;
      fetch(cancelUrl, {
        method: "POST",
        headers: {
          "X-CSRFToken": csrfToken,
          "X-Requested-With": "XMLHttpRequest",
        },
      })
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          if (data.ok) {
            showCancelledState();
          } else {
            console.error("[OrderEdit:cancel]", data.error);
            cancelBtn.disabled = false;
          }
        })
        .catch(function (err) {
          console.error("[OrderEdit:cancel]", err);
          cancelBtn.disabled = false;
        });
    });
  }

  function showCancelledState() {
    // Remove edit controls
    document.querySelectorAll(".order-edit-controls").forEach(function (el) {
      el.remove();
    });
    if (cancelBtn) cancelBtn.remove();

    // Show cancelled alert
    var alert = document.createElement("div");
    alert.className = "alert alert-danger text-center mt-3";
    alert.innerHTML =
      '<i class="bi bi-x-circle"></i> Замовлення скасовано';
    var container = document.querySelector(".container.mt-3");
    if (container) container.prepend(alert);
  }
})();
