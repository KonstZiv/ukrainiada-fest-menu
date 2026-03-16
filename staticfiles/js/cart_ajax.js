/**
 * AJAX cart controls — intercepts +/- form submits and updates DOM
 * without full page reload. Falls back to normal POST if JS fails.
 */
(function () {
    "use strict";

    document.addEventListener("submit", function (e) {
        var form = e.target;
        if (!form.matches || !form.matches(".cart-control-form")) return;

        e.preventDefault();

        var url = form.action;
        var csrfToken = form.querySelector('[name="csrfmiddlewaretoken"]').value;
        var formData = new FormData(form);

        fetch(url, {
            method: "POST",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": csrfToken,
            },
            body: formData,
        })
            .then(function (resp) {
                return resp.json();
            })
            .then(function (data) {
                updateDishControls(data.dish_id, data.dish_qty);
                updateFab(data.cart_count, data.cart_total);
            })
            .catch(function () {
                // Fallback: submit normally
                form.submit();
            });
    });

    function updateDishControls(dishId, qty) {
        // Find all cart-control containers for this dish
        document.querySelectorAll('[data-dish-id="' + dishId + '"]').forEach(function (container) {
            var minusBtn = container.querySelector(".cart-minus");
            var qtySpan = container.querySelector(".cart-qty");

            if (qty > 0) {
                // Show minus + quantity
                if (!minusBtn) {
                    // Need to create minus button — reload fallback
                    location.reload();
                    return;
                }
                minusBtn.style.display = "";
                if (qtySpan) qtySpan.textContent = qty;
                if (qtySpan) qtySpan.style.display = "";
            } else {
                // Hide minus + quantity
                if (minusBtn) minusBtn.style.display = "none";
                if (qtySpan) qtySpan.style.display = "none";
            }
        });
    }

    function updateFab(count, total) {
        var fab = document.querySelector(".btn-fab-order");
        if (!fab) return;

        var pill = fab.querySelector(".cart-pill");
        var totalSpan = fab.querySelector(".cart-total");

        if (pill) {
            if (count > 0) {
                pill.textContent = count;
                pill.style.display = "";
            } else {
                pill.style.display = "none";
            }
        }

        if (totalSpan) {
            totalSpan.textContent = "€" + parseFloat(total).toFixed(2).replace(".", ",");
        }
    }
})();
