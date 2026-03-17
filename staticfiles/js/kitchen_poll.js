/**
 * kitchen_poll.js — Temporary polling for kitchen dashboard auto-refresh.
 *
 * TODO: remove this file when SSE/ASGI is deployed.
 * Reads window.KITCHEN_POLL_URL and window.KITCHEN_LAST_ESCALATION_ID
 * set by the dashboard template.
 */
(function () {
  "use strict";

  var POLL_INTERVAL = 20000; // 20 seconds
  var pollUrl = window.KITCHEN_POLL_URL;
  if (!pollUrl) return;

  var lastEscId = window.KITCHEN_LAST_ESCALATION_ID || 0;
  var knownCounts = null; // {pending, taken, done}
  var timerId = null;

  // -----------------------------------------------------------------------
  // Audio — Web Audio API beep (no MP3 needed)
  // -----------------------------------------------------------------------
  var audioCtx = null;
  var soundReady = false;

  function initAudio() {
    if (soundReady) return;
    try {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      soundReady = true;
      var banner = document.getElementById("sound-banner");
      if (banner) banner.style.display = "none";
    } catch (e) {
      /* browser does not support Web Audio */
    }
  }

  // Activate audio on first user interaction (browser autoplay policy)
  document.addEventListener("click", function () { initAudio(); }, { once: true });
  document.addEventListener("touchstart", function () { initAudio(); }, { once: true });

  function playBeep(freq, duration) {
    if (!audioCtx || !soundReady) return;
    freq = freq || 880;
    duration = duration || 0.4;
    var osc = audioCtx.createOscillator();
    var gain = audioCtx.createGain();
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.type = "sine";
    osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
    gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + duration);
    osc.start(audioCtx.currentTime);
    osc.stop(audioCtx.currentTime + duration);
  }

  function playEscalationBeep() {
    playBeep(880, 0.3);
    setTimeout(function () { playBeep(1046, 0.3); }, 350);
  }

  function playNewOrderBeep() {
    playBeep(660, 0.2);
  }

  // -----------------------------------------------------------------------
  // Polling
  // -----------------------------------------------------------------------
  function poll() {
    var url = pollUrl + "?last_esc=" + lastEscId;
    fetch(url, { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        // Check for new escalation
        if (data.has_new_escalation && data.last_escalation_id > lastEscId) {
          lastEscId = data.last_escalation_id;
          playEscalationBeep();
          location.reload();
          return;
        }

        // Check if counts changed — reload for fresh data
        if (knownCounts !== null) {
          if (
            data.pending_count !== knownCounts.pending ||
            data.taken_count !== knownCounts.taken ||
            data.done_count !== knownCounts.done
          ) {
            // Counts changed — a soft beep for new pending work
            if (data.pending_count > knownCounts.pending) {
              playNewOrderBeep();
            }
            location.reload();
            return;
          }
        }

        // Store current counts for next comparison
        knownCounts = {
          pending: data.pending_count,
          taken: data.taken_count,
          done: data.done_count,
        };

        // Update badges in-place (no reload needed)
        setText("pending-count", data.pending_count);
        setText("taken-count", data.taken_count);
        setText("done-count", data.done_count);
      })
      .catch(function (err) {
        console.warn("[KitchenPoll] Error:", err);
      });
  }

  function setText(id, val) {
    var el = document.getElementById(id);
    if (el) el.textContent = val;
  }

  // Initialize known counts from current page
  knownCounts = {
    pending: parseInt(getText("pending-count") || "0", 10),
    taken: parseInt(getText("taken-count") || "0", 10),
    done: parseInt(getText("done-count") || "0", 10),
  };

  function getText(id) {
    var el = document.getElementById(id);
    return el ? el.textContent.trim() : "0";
  }

  timerId = setInterval(poll, POLL_INTERVAL);

  window.addEventListener("beforeunload", function () {
    clearInterval(timerId);
  });
})();
