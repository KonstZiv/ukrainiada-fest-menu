/**
 * OrderTracker — SSE client for live order tracking on order_detail page.
 * Updates ticket statuses, progress bar with PWM partial animation,
 * and payment strip without page reload.
 * Uses textContent (not innerHTML) for XSS safety.
 */
(function () {
    "use strict";

    // Maps order status → visual step index (must match _build_progress_steps in views.py)
    const STATUS_TO_STEP = {
        "draft": -1,
        "submitted": 0,
        "accepted": 1,
        "verified": 2,
        "in_progress": 3,
        "ready": 4,
        "delivered": 5,
    };

    // Step keys that support partial progress (PWM pulse)
    const PARTIAL_STEP_KEYS = {
        "cooking": { counterField: "takenCount" },
        "ready": { counterField: "doneCount" },
        "delivered": { counterField: "deliveredCount" },
    };

    class OrderTracker {
        constructor(orderId, sseUrl, container) {
            this.orderId = orderId;
            this.sseUrl = sseUrl;
            this.source = null;

            // Read ticket counts from data attributes for partial progress
            this.totalTickets = parseInt(container.dataset.totalTickets || "0", 10);
            this.takenCount = parseInt(container.dataset.takenCount || "0", 10);
            this.doneCount = parseInt(container.dataset.doneCount || "0", 10);
            this.deliveredCount = parseInt(container.dataset.deliveredCount || "0", 10);

            console.log("[OrderTracker] init total=" + this.totalTickets +
                " taken=" + this.takenCount +
                " done=" + this.doneCount +
                " delivered=" + this.deliveredCount);

            // Apply initial partial progress animations
            this._applyPartialProgress();

            this.connect();
        }

        connect() {
            this._reconnectAttempts = 0;
            this.source = new EventSource(this.sseUrl);
            console.log("[OrderTracker] connecting to", this.sseUrl);
            this.source.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    console.log("[OrderTracker] event:", data.type, data);
                    this.handleEvent(data);
                } catch (e) {
                    // Ignore non-JSON keepalive messages
                }
            };
            this.source.onopen = () => {
                this._reconnectAttempts = 0;
                console.log("[OrderTracker] connected");
            };
            this.source.onerror = () => {
                this._reconnectAttempts++;
                console.warn("[OrderTracker] error, attempt", this._reconnectAttempts);
                if (this._reconnectAttempts >= 3) {
                    this.source.close();
                    console.warn("[OrderTracker] gave up after 3 attempts");
                }
            };
        }

        handleEvent(data) {
            switch (data.type) {
                case "ticket_taken":
                    this.takenCount++;
                    this.updateProgress("in_progress");
                    this._applyPartialProgress();
                    console.log("[OrderTracker] ticket_taken → taken=" + this.takenCount);
                    break;
                case "ticket_done":
                    this.doneCount++;
                    if (this.doneCount >= this.totalTickets) {
                        this.updateProgress("ready");
                    }
                    this._applyPartialProgress();
                    console.log("[OrderTracker] ticket_done → done=" + this.doneCount + "/" + this.totalTickets);
                    break;
                case "dish_collecting":
                    break;
                case "dish_delivered":
                    this.deliveredCount++;
                    // Soft flow: server auto-completes take+done when waiter delivers
                    if (this.takenCount < this.deliveredCount) this.takenCount = this.deliveredCount;
                    if (this.doneCount < this.deliveredCount) this.doneCount = this.deliveredCount;
                    this._applyPartialProgress();
                    console.log("[OrderTracker] dish_delivered → delivered=" + this.deliveredCount + "/" + this.totalTickets);
                    break;
                case "order_accepted":
                    this.updateProgress("accepted");
                    break;
                case "order_verified":
                    this.updateProgress("verified");
                    break;
                case "order_ready":
                    this.updateProgress("ready");
                    this._applyPartialProgress();
                    this.showGlobalMessage("\uD83C\uDF89 " + gettext("Всі страви готові!"));
                    break;
                case "order_delivered":
                    this.updateProgress("delivered");
                    // Force-complete all counters (soft flow may have skipped events)
                    this.takenCount = this.totalTickets;
                    this.doneCount = this.totalTickets;
                    this.deliveredCount = this.totalTickets;
                    this._applyPartialProgress();
                    this.showGlobalMessage("\u2705 " + gettext("Замовлення доставлено! Смачного!"));
                    break;
                case "order_paid":
                    // Force-complete everything before showing paid
                    this.takenCount = this.totalTickets;
                    this.doneCount = this.totalTickets;
                    this.deliveredCount = this.totalTickets;
                    this.updateProgress("delivered");
                    this._applyPartialProgress();
                    this._updatePaymentStrip(true);
                    this.showGlobalMessage("\u2705 " + gettext("Оплату прийнято. Дякуємо!"));
                    this.disconnect();
                    break;
                case "order_updated":
                    location.reload();
                    break;
                case "order_cancelled":
                    this.showGlobalMessage("\u274C " + gettext("Замовлення скасовано"));
                    this.disconnect();
                    break;
                case "escalation_created":
                    this.showGlobalMessage("\u26A0\uFE0F " + gettext("Ваше звернення прийнято"));
                    break;
                case "escalation_acknowledged":
                    this.showGlobalMessage("\uD83D\uDC4D " + interpolate(gettext("%(by)s працює над вашим питанням"), {by: data.by || ""}, true));
                    break;
                case "escalation_resolved":
                    this.showGlobalMessage("\u2705 " + (data.note || gettext("Вирішено")));
                    break;
            }
        }

        setTicketStatus(ticketId, status, icon, text) {
            const row = document.querySelector('[data-ticket-id="' + ticketId + '"]');
            if (!row) return;
            const iconEl = row.querySelector(".ticket-icon");
            const detailEl = row.querySelector(".ticket-detail");
            if (iconEl) {
                iconEl.textContent = icon;
                iconEl.dataset.status = status;
            }
            if (detailEl) {
                detailEl.textContent = text;
            }
            row.classList.add("status-updated");
            setTimeout(() => row.classList.remove("status-updated"), 2000);
        }

        updateProgress(newStatus) {
            const bar = document.querySelector(".order-progress");
            const targetStep = STATUS_TO_STEP[newStatus];
            console.log("[OrderTracker] updateProgress status=" + newStatus + " targetStep=" + targetStep);
            if (!bar || targetStep === undefined) return;

            bar.querySelectorAll(".progress-step").forEach((step) => {
                const idx = parseInt(step.dataset.stepIndex, 10);
                const key = step.dataset.stepKey;

                // For binary steps: done if index <= target
                if (!PARTIAL_STEP_KEYS[key]) {
                    step.classList.remove("done", "active");
                    if (idx <= targetStep) step.classList.add("done");
                }
                // Partial steps handled by _applyPartialProgress
            });
        }

        /**
         * Apply PWM-like pulse animation to partial-progress steps.
         * Duty cycle = (completed / total) of the animation cycle is "bright",
         * rest is "faded". When progress reaches 1.0, step becomes solid "done".
         */
        _applyPartialProgress() {
            if (this.totalTickets === 0) return;

            const progressMap = {
                "cooking": this.takenCount / this.totalTickets,
                "ready": this.doneCount / this.totalTickets,
                "delivered": this.deliveredCount / this.totalTickets,
            };

            const bar = document.querySelector(".order-progress");
            if (!bar) return;

            bar.querySelectorAll(".progress-step").forEach((step) => {
                const key = step.dataset.stepKey;
                if (!(key in progressMap)) return;

                const progress = Math.min(progressMap[key], 1.0);
                const iconEl = step.querySelector(".step-icon");
                if (!iconEl) return;

                step.classList.remove("done", "active");

                if (progress >= 1.0) {
                    // Fully done
                    step.classList.add("done");
                    iconEl.style.animation = "";
                    console.log("[OrderTracker] partial " + key + " = 1.0 → done");
                } else if (progress > 0) {
                    // Partial — apply PWM animation with random phase offset
                    step.classList.add("active");
                    this._injectPWMKeyframes(key, progress);
                    if (!this._pwmDelays) this._pwmDelays = {};
                    if (!(key in this._pwmDelays)) {
                        this._pwmDelays[key] = (Math.random() * 0.5).toFixed(2);
                    }
                    iconEl.style.animation = "pwm-" + key + " 3s " + this._pwmDelays[key] + "s infinite linear";
                    console.log("[OrderTracker] partial " + key + " = " + progress.toFixed(2) + " → PWM pulse");
                } else {
                    // Not started — stays faded (default CSS)
                    iconEl.style.animation = "";
                }
            });
        }

        /**
         * Inject CSS @keyframes for PWM-style pulse.
         * Bright phase = progress fraction, then smooth fade to dim.
         * 5% transition zones for gradual opacity changes.
         */
        _injectPWMKeyframes(stepKey, progress) {
            const id = "pwm-keyframes-" + stepKey;
            let styleEl = document.getElementById(id);
            if (!styleEl) {
                styleEl = document.createElement("style");
                styleEl.id = id;
                document.head.appendChild(styleEl);
            }

            const pct = Math.round(progress * 100);
            const fadeOut = Math.min(pct + 5, 95);
            // Bright → fade out → dim → fade in → loop
            styleEl.textContent =
                "@keyframes pwm-" + stepKey + " {" +
                "  0% { opacity: 1; }" +
                "  " + pct + "% { opacity: 1; }" +
                "  " + fadeOut + "% { opacity: 0.15; }" +
                "  93% { opacity: 0.15; }" +
                "  100% { opacity: 1; }" +
                "}";
        }

        _updatePaymentStrip(isPaid) {
            const strip = document.getElementById("payment-strip");
            if (!strip) return;
            console.log("[OrderTracker] updatePaymentStrip paid=" + isPaid);
            strip.classList.remove("paid", "unpaid");
            if (isPaid) {
                strip.classList.add("paid");
                strip.textContent = strip.dataset.paidText || gettext("СПЛАЧЕНО");
            } else {
                strip.classList.add("unpaid");
            }
        }

        showGlobalMessage(text) {
            const el = document.getElementById("order-global-status");
            if (!el) return;
            el.textContent = text;
            el.classList.remove("d-none");
        }

        disconnect() {
            console.log("[OrderTracker] disconnect — closing SSE connection");
            if (this.source) {
                this.source.close();
                this.source = null;
            }
        }
    }

    // Auto-init from data attributes
    document.addEventListener("DOMContentLoaded", () => {
        const container = document.getElementById("order-tracker");
        if (!container) return;
        const orderId = parseInt(container.dataset.orderId, 10);
        const sseUrl = container.dataset.sseUrl;
        if (orderId && sseUrl) {
            window.orderTracker = new OrderTracker(orderId, sseUrl, container);
        }
    });
})();
