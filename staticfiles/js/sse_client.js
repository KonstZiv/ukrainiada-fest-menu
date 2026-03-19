/**
 * Festival Menu SSE Client
 * Connects to /events/stream/ and updates DOM on incoming events.
 * Vanilla JS — no dependencies.
 */
(function () {
  'use strict';

  if (typeof EventSource === 'undefined') return;

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

  source.addEventListener('message', function (e) {
    var data;
    try {
      data = JSON.parse(e.data);
    } catch (err) {
      console.error('[SSE] Parse error:', err);
      return;
    }
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
      case 'kitchen_escalation':
      case 'payment_escalation':
        onEscalation(data);
        break;
    }
  }

  function onTicketDone(data) {
    var el = document.querySelector(
      '[data-ticket-id="' + data.ticket_id + '"] .ticket-status'
    );
    if (el) {
      el.textContent = 'Готово';
      el.className = 'ticket-status badge bg-success';
    }
  }

  function onOrderReady(data) {
    var card = document.querySelector('[data-order-id="' + data.order_id + '"]');
    if (card) {
      card.classList.add('border-success');
      var btn = card.querySelector('.btn-deliver');
      if (btn) btn.style.display = 'block';
    }
    showFlash('Замовлення #' + data.order_id + ' готове!', 'success');
  }

  function onTicketTaken(data) {
    var el = document.querySelector(
      '[data-ticket-id="' + data.ticket_id + '"] .ticket-status'
    );
    if (el) {
      el.textContent = 'Готується (' + data.by + ')';
      el.className = 'ticket-status badge bg-info';
    }
  }

  function onOrderApproved(data) {
    var counter = document.getElementById('pending-count');
    if (counter) {
      counter.textContent = parseInt(counter.textContent || '0', 10) + 1;
    }
    showFlash('Нове замовлення #' + data.order_id, 'info');
    sseBeep(660, 0.2); // soft beep for new order
  }

  var escalationLabels = {
    kitchen_escalation: 'Кухня',
    payment_escalation: 'Оплата',
  };

  function onEscalation(data) {
    var id = data.ticket_id || data.order_id;
    var label = escalationLabels[data.type] || data.type;
    showFlash('Ескалація! ' + label + ' #' + id, 'danger');
    var badge = document.getElementById('escalation-badge');
    if (badge) badge.style.display = 'inline';
    // Audio alert — double beep for escalation
    sseBeep(880, 0.3);
    setTimeout(function () { sseBeep(1046, 0.3); }, 350);
  }

  function showFlash(message, type) {
    var container = document.getElementById('flash-container');
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
