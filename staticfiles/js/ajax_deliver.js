/**
 * AJAX handler for delivery/handoff forms.
 * Forms with class "ajax-deliver" submit via fetch() instead of full page reload.
 * On success: the closest list-group-item fades out and is removed.
 */
document.addEventListener("submit", function (e) {
  const form = e.target.closest("form.ajax-deliver");
  if (!form) return;
  e.preventDefault();

  console.log("[AjaxDeliver] submit intercepted url=" + form.action);

  const btn = form.querySelector("button[type=submit]");
  if (btn) btn.disabled = true;

  const formData = new FormData(form);
  fetch(form.action, {
    method: "POST",
    headers: { "X-Requested-With": "XMLHttpRequest" },
    body: formData,
  })
    .then(function (resp) {
      console.log("[AjaxDeliver] response status=" + resp.status);
      return resp.json();
    })
    .then(function (data) {
      console.log("[AjaxDeliver] data:", JSON.stringify(data));
      if (data.ok) {
        // Replace button with "віддано" badge
        var parent = form.parentElement;
        form.remove();
        var badge = document.createElement("span");
        badge.className = "badge bg-secondary";
        badge.style.fontSize = "0.65rem";
        badge.textContent = gettext("доставлено");
        parent.insertBefore(badge, parent.firstChild);
        console.log("[AjaxDeliver] badge inserted, form removed");

        // Update row styling
        var row = parent.closest(".list-group-item");
        if (row) {
          row.classList.remove("list-group-item-danger", "list-group-item-warning", "list-group-item-success");
          row.style.opacity = "0.5";
          console.log("[AjaxDeliver] row faded out");
        }

        // Reload page when all dishes delivered (updates order status + badges)
        if (data.all_delivered) {
          console.log("[AjaxDeliver] all_delivered — reloading in 500ms");
          setTimeout(function () { location.reload(); }, 500);
        }
      } else {
        console.warn("[AjaxDeliver] response data.ok is falsy:", data);
        if (btn) btn.disabled = false;
      }
    })
    .catch(function (err) {
      console.error("[AjaxDeliver] fetch failed:", err);
      if (btn) btn.disabled = false;
    });
});
