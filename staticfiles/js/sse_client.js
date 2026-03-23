/**
 * Festival Menu SSE Client
 * Connects to /events/stream/ and updates DOM on incoming events.
 * Includes navbar badge system for persistent unseen event tracking.
 * Vanilla JS — no dependencies.
 */
(function () {
  'use strict';

  if (typeof EventSource === 'undefined') return;

  // --- Dashboard detection ---
  var _isKitchenDashboard = !!(
    document.querySelector('.kitchen-kanban') ||
    document.querySelector('.kitchen-tab-pills')
  );
  var _isWaiterDashboard = !!document.querySelector('[data-poll-count]');
  console.log('[SSE] dashboard detection: kitchen=' + _isKitchenDashboard + ' waiter=' + _isWaiterDashboard);

  var _reloadScheduled = false;

  function scheduleReload(delayMs) {
    if (_reloadScheduled) return;
    _reloadScheduled = true;
    console.log('[SSE] scheduling page reload in ' + delayMs + 'ms');
    setTimeout(function () { location.reload(); }, delayMs);
  }

  // --- Navbar badge system (localStorage-backed) ---
  var BADGE_ORDERS_KEY = 'sse_unseen_orders';
  var BADGE_KITCHEN_KEY = 'sse_unseen_kitchen';

  function updateNavBadge(elementId, storageKey, delta) {
    var count = parseInt(localStorage.getItem(storageKey) || '0', 10) + delta;
    if (count < 0) count = 0;
    localStorage.setItem(storageKey, String(count));
    _renderBadge(elementId, count);
  }

  function clearNavBadge(elementId, storageKey) {
    localStorage.removeItem(storageKey);
    _renderBadge(elementId, 0);
  }

  function _renderBadge(elementId, count) {
    var badge = document.getElementById(elementId);
    if (!badge) return;
    if (count > 0) {
      badge.textContent = count;
      badge.style.display = '';
    } else {
      badge.style.display = 'none';
    }
  }

  // Restore badges from localStorage on page load
  _renderBadge('nav-badge-orders', parseInt(localStorage.getItem(BADGE_ORDERS_KEY) || '0', 10));
  _renderBadge('nav-badge-kitchen', parseInt(localStorage.getItem(BADGE_KITCHEN_KEY) || '0', 10));

  // Clear badge when user is on the relevant dashboard
  if (_isWaiterDashboard) {
    clearNavBadge('nav-badge-orders', BADGE_ORDERS_KEY);
  }
  if (_isKitchenDashboard) {
    clearNavBadge('nav-badge-kitchen', BADGE_KITCHEN_KEY);
  }

  // --- Audio beep via Web Audio API ---
  var _audioCtx = null;
  var _soundReady = false;

  function _initAudio() {
    if (_soundReady) return;
    try {
      _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      _soundReady = true;
    } catch (e) { /* unsupported */ }
  }

  document.addEventListener('click', function () { _initAudio(); }, { once: true });
  document.addEventListener('touchstart', function () { _initAudio(); }, { once: true });

  function sseBeep(freq, duration) {
    if (!_audioCtx || !_soundReady) return;
    var osc = _audioCtx.createOscillator();
    var gain = _audioCtx.createGain();
    osc.connect(gain);
    gain.connect(_audioCtx.destination);
    osc.type = 'sine';
    osc.frequency.setValueAtTime(freq || 880, _audioCtx.currentTime);
    gain.gain.setValueAtTime(0.3, _audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, _audioCtx.currentTime + (duration || 0.4));
    osc.start(_audioCtx.currentTime);
    osc.stop(_audioCtx.currentTime + (duration || 0.4));
  }

  var MAX_RECONNECT = 3;
  var reconnectAttempts = 0;
  var source = new EventSource(window.SSE_STREAM_URL || '/events/stream/');
  console.log('[SSE] connecting to', window.SSE_STREAM_URL || '/events/stream/');

  source.addEventListener('message', function (e) {
    var data;
    try {
      data = JSON.parse(e.data);
    } catch (err) {
      console.error('[SSE] Parse error:', err);
      return;
    }
    console.log('[SSE] event:', data.type, data);
    handleEvent(data);
  });

  source.onopen = function () {
    reconnectAttempts = 0;
    setConnectionStatus(true);
  };

  source.onerror = function () {
    reconnectAttempts++;
    setConnectionStatus(false);
    console.warn('[SSE] Connection lost, attempt ' + reconnectAttempts);
    if (reconnectAttempts >= MAX_RECONNECT) {
      source.close();
      console.warn('[SSE] Max reconnect attempts reached, giving up');
    }
  };

  function setConnectionStatus(connected) {
    var indicator = document.getElementById('connection-indicator');
    console.log('[SSE] setConnectionStatus connected=' + connected + ' indicator_found=' + !!indicator);
    if (!indicator) return;
    if (connected) {
      indicator.className = 'badge bg-success';
      indicator.textContent = 'Live';
    } else {
      indicator.className = 'badge bg-danger';
      indicator.textContent = 'Offline';
    }
  }

  function handleEvent(data) {
    switch (data.type) {
      case 'order_submitted':
        onOrderSubmitted(data);
        break;
      case 'ticket_done':
        onTicketDone(data);
        break;
      case 'order_ready':
        onOrderReady(data);
        break;
      case 'ticket_taken':
        onTicketTaken(data);
        break;
      case 'order_approved':
        onOrderApproved(data);
        break;
      case 'ticket_delivered':
        onTicketDelivered(data);
        break;
      case 'kitchen_escalation':
      case 'payment_escalation':
      case 'visitor_escalation':
        onEscalation(data);
        break;
    }
  }

  function onOrderSubmitted(data) {
    console.log('[SSE] onOrderSubmitted order=' + data.order_id);
    showFlash('Нове замовлення #' + data.order_id + ' від клієнта', 'info');
    sseBeep(660, 0.2);
    updateNavBadge('nav-badge-orders', BADGE_ORDERS_KEY, 1);
    if (_isWaiterDashboard) {
      scheduleReload(2000);
    }
  }

  function onTicketDone(data) {
    var el = document.querySelector(
      '[data-ticket-id="' + data.ticket_id + '"] .ticket-status'
    );
    console.log('[SSE] onTicketDone ticket=' + data.ticket_id + ' el_found=' + !!el);
    if (el) {
      el.textContent = 'Готово';
      el.className = 'ticket-status badge bg-success';
    }
    showFlash('Страва готова: ' + (data.dish || '#' + data.ticket_id), 'success');
    updateNavBadge('nav-badge-orders', BADGE_ORDERS_KEY, 1);
    if (_isWaiterDashboard) {
      scheduleReload(2000);
    }
  }

  function onOrderReady(data) {
    var card = document.querySelector('[data-order-id="' + data.order_id + '"]');
    console.log('[SSE] onOrderReady order=' + data.order_id + ' card_found=' + !!card);
    if (card) {
      card.classList.add('border-success');
      var btn = card.querySelector('.btn-deliver');
      console.log('[SSE] onOrderReady btn-deliver found=' + !!btn);
      if (btn) btn.style.display = 'block';
    }
    showFlash('Замовлення #' + data.order_id + ' готове!', 'success');
    updateNavBadge('nav-badge-orders', BADGE_ORDERS_KEY, 1);
    if (_isWaiterDashboard) {
      scheduleReload(2000);
    }
  }

  function onTicketTaken(data) {
    var el = document.querySelector(
      '[data-ticket-id="' + data.ticket_id + '"] .ticket-status'
    );
    console.log('[SSE] onTicketTaken ticket=' + data.ticket_id + ' by=' + data.by + ' el_found=' + !!el);
    if (el) {
      el.textContent = 'Готується (' + data.by + ')';
      el.className = 'ticket-status badge bg-info';
    }
  }

  function onOrderApproved(data) {
    var counter = document.getElementById('pending-count');
    var oldCount = counter ? counter.textContent : 'N/A';
    console.log('[SSE] onOrderApproved order=' + data.order_id + ' pending_counter_found=' + !!counter + ' old_count=' + oldCount);
    if (counter) {
      counter.textContent = parseInt(counter.textContent || '0', 10) + 1;
    }
    showFlash('Замовлення #' + data.order_id + ' на кухні', 'info');
    sseBeep(660, 0.2);
    updateNavBadge('nav-badge-kitchen', BADGE_KITCHEN_KEY, 1);
    if (_isKitchenDashboard) {
      scheduleReload(2000);
    }
  }

  function onTicketDelivered(data) {
    console.log('[SSE] onTicketDelivered ticket=' + data.ticket_id + ' status=' + data.prev_status);
    updateNavBadge('nav-badge-kitchen', BADGE_KITCHEN_KEY, 1);
    if (_isKitchenDashboard) {
      // Determine which badge to decrement based on prev_status
      var statusToBadge = { pending: 'pending', taken: 'taken', done: 'done' };
      var badgeKey = statusToBadge[data.prev_status] || 'done';
      var badgeIds = { pending: 'pending-count', taken: 'taken-count', done: 'done-count' };
      var tabHrefs = { pending: '?tab=queue', taken: '?tab=in_progress', done: '?tab=done' };

      // Remove ticket card if visible
      var card = document.querySelector('[data-ticket-id="' + data.ticket_id + '"]');
      if (card) {
        card.style.transition = 'opacity 0.3s';
        card.style.opacity = '0';
        setTimeout(function () {
          var group = card.closest('.kitchen-order-group');
          card.remove();
          if (group && group.querySelectorAll('[data-ticket-id]').length === 0) {
            group.remove();
          }
        }, 300);
      }

      // Update badge for the correct column (desktop)
      var desktopBadge = document.getElementById(badgeIds[badgeKey]);
      if (desktopBadge) {
        desktopBadge.textContent = Math.max(0, parseInt(desktopBadge.textContent, 10) - 1);
      }
      // Update badge (mobile pill)
      var mobileBadge = document.querySelector(
        ".kitchen-tab-pills a[href='" + tabHrefs[badgeKey] + "'] .badge"
      );
      if (mobileBadge) {
        var val = Math.max(0, parseInt(mobileBadge.textContent, 10) - 1);
        mobileBadge.textContent = val;
        if (val === 0) mobileBadge.style.display = 'none';
      }
    }
  }

  var escalationLabels = {
    kitchen_escalation: 'Кухня',
    payment_escalation: 'Оплата',
  };

  function onEscalation(data) {
    var id = data.ticket_id || data.order_id;
    var label = escalationLabels[data.type] || data.type;
    console.log('[SSE] onEscalation type=' + data.type + ' id=' + id + ' level=' + data.level);
    showFlash('Ескалація! ' + label + ' #' + id, 'danger');
    var badge = document.getElementById('escalation-badge');
    console.log('[SSE] onEscalation badge_found=' + !!badge);
    if (badge) badge.style.display = 'inline';
    sseBeep(880, 0.3);
    setTimeout(function () { sseBeep(1046, 0.3); }, 350);
    if (_isKitchenDashboard || _isWaiterDashboard) {
      scheduleReload(2000);
    }
  }

  function showFlash(message, type) {
    var container = document.getElementById('flash-container');
    console.log('[SSE] showFlash type=' + type + ' msg="' + message + '" container_found=' + !!container);
    if (!container) return;
    var el = document.createElement('div');
    el.className = 'alert alert-' + type + ' alert-dismissible fade show';
    var span = document.createElement('span');
    span.textContent = message;
    el.appendChild(span);
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn-close';
    btn.setAttribute('data-bs-dismiss', 'alert');
    el.appendChild(btn);
    container.prepend(el);
    setTimeout(function () {
      if (el.parentNode) el.remove();
    }, 8000);
  }
})();
