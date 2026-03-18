/**
 * AJAX handler for delivery/handoff forms.
 * Forms with class "ajax-deliver" submit via fetch() instead of full page reload.
 * On success: the closest list-group-item fades out and is removed.
 */
document.addEventListener("submit", function (e) {
  const form = e.target.closest("form.ajax-deliver");
  if (!form) return;
  e.preventDefault();

  const btn = form.querySelector("button[type=submit]");
  if (btn) btn.disabled = true;

  const formData = new FormData(form);
  fetch(form.action, {
    method: "POST",
    headers: { "X-Requested-With": "XMLHttpRequest" },
    body: formData,
  })
    .then(function (resp) { return resp.json(); })
    .then(function (data) {
      if (data.ok) {
        // Replace button with "віддано" badge
        var parent = form.parentElement;
        form.remove();
        var badge = document.createElement("span");
        badge.className = "badge bg-secondary";
        badge.style.fontSize = "0.65rem";
        badge.textContent = "віддано";
        parent.insertBefore(badge, parent.firstChild);

        // Update row styling
        var row = parent.closest(".list-group-item");
        if (row) {
          row.classList.remove("list-group-item-danger", "list-group-item-warning", "list-group-item-success");
          row.style.opacity = "0.5";
        }
      }
    })
    .catch(function () {
      if (btn) btn.disabled = false;
    });
});
