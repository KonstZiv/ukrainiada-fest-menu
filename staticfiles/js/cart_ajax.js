/**
 * AJAX cart controls — intercepts +/- form submits and updates DOM
 * without full page reload. Falls back to normal POST if JS fails.
 */
(function () {
    "use strict";

    function formatPrice(val) {
        return "€" + parseFloat(val).toFixed(2).replace(".", ",");
    }

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
                updateDishControls(data.dish_id, data.dish_qty, data.dish_price);
                updateCartTotal(data.cart_total);
                updateFab(data.cart_count, data.cart_total);
                if (data.dish_qty === 0) {
                    removeCartRow(data.dish_id);
                }
            })
            .catch(function () {
                form.submit();
            });
    });

    function updateDishControls(dishId, qty, dishPrice) {
        document.querySelectorAll('[data-dish-id="' + dishId + '"]').forEach(function (container) {
            var minusBtn = container.querySelector(".cart-minus");
            var qtySpan = container.querySelector(".cart-qty");

            if (qty > 0) {
                if (!minusBtn) {
                    location.reload();
                    return;
                }
                minusBtn.classList.remove("d-none");
                minusBtn.classList.add("d-inline");
                if (qtySpan) {
                    qtySpan.textContent = qty;
                    qtySpan.classList.remove("d-none");
                    qtySpan.classList.add("d-inline");
                }
                // Update subtotal in cart row
                var row = container.closest("[data-cart-row]");
                if (row && dishPrice) {
                    var subtotalSpan = row.querySelector(".cart-subtotal");
                    if (subtotalSpan) {
                        subtotalSpan.textContent = formatPrice(qty * parseFloat(dishPrice));
                    }
                }
            } else {
                if (minusBtn) {
                    minusBtn.classList.remove("d-inline");
                    minusBtn.classList.add("d-none");
                }
                if (qtySpan) {
                    qtySpan.classList.remove("d-inline");
                    qtySpan.classList.add("d-none");
                }
            }
        });
    }

    function removeCartRow(dishId) {
        var row = document.querySelector('[data-cart-row="' + dishId + '"]');
        if (row) {
            row.remove();
        }
        // Check if cart is now empty
        var cartItems = document.getElementById("cart-items");
        if (cartItems && cartItems.children.length === 0) {
            showEmptyCart();
        }
    }

    function showEmptyCart() {
        var cartItems = document.getElementById("cart-items");
        var cartFooter = document.getElementById("cart-footer");
        var heading = document.querySelector("h5.text-muted");
        if (cartItems) cartItems.remove();
        if (cartFooter) cartFooter.remove();
        if (heading) heading.remove();

        var container = document.querySelector(".container.mt-3");
        if (container) {
            var alert = document.createElement("div");
            alert.className = "alert alert-info";
            alert.id = "cart-empty";
            alert.innerHTML =
                '<i class="bi bi-info-circle"></i> Ви ще нічого не обрали. ' +
                '<a href="/menu/dishes/">Перейти до меню</a>';
            container.appendChild(alert);
        }
    }

    function updateCartTotal(total) {
        var totalValue = document.querySelector(".cart-total-value");
        if (totalValue) {
            totalValue.textContent = formatPrice(total);
        }
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
            totalSpan.textContent = formatPrice(total);
        }
    }
})();
