/**
 * waiter_poll.js — Temporary polling for waiter board auto-refresh.
 *
 * TODO: remove this file when SSE/ASGI is deployed.
 * Reads window.WAITER_POLL_URL set by the waiter_order_list template.
 */
(function () {
  "use strict";

  var POLL_INTERVAL = window.WAITER_POLL_INTERVAL || 15000;
  var pollUrl = window.WAITER_POLL_URL;
  if (!pollUrl) return;

  var knownCounts = null;

  function initCounts() {
    var badges = document.querySelectorAll("[data-poll-count]");
    knownCounts = {};
    badges.forEach(function (el) {
      knownCounts[el.dataset.pollCount] = parseInt(el.textContent) || 0;
    });
  }

  function poll() {
    fetch(pollUrl)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (!knownCounts) { initCounts(); return; }
        var changed = (
          data.new_count !== knownCounts.new ||
          data.my_count !== knownCounts.my ||
          data.unpaid_count !== knownCounts.unpaid
        );
        if (changed) {
          location.reload();
        }
      })
      .catch(function (err) { console.warn("[waiter-poll]", err); });
  }

  initCounts();
  setInterval(poll, POLL_INTERVAL);
})();
