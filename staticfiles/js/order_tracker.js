/**
 * OrderTracker — SSE client for live order tracking on order_detail page.
 * Updates ticket statuses and progress bar without page reload.
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
        "paid": 6,
    };

    class OrderTracker {
        constructor(orderId, sseUrl) {
            this.orderId = orderId;
            this.sseUrl = sseUrl;
            this.source = null;
            this.connect();
        }

        connect() {
            this._reconnectAttempts = 0;
            this.source = new EventSource(this.sseUrl);
            this.source.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleEvent(data);
                } catch (e) {
                    // Ignore non-JSON keepalive messages
                }
            };
            this.source.onopen = () => {
                this._reconnectAttempts = 0;
            };
            this.source.onerror = () => {
                this._reconnectAttempts++;
                if (this._reconnectAttempts >= 3) {
                    this.source.close();
                }
            };
        }

        handleEvent(data) {
            switch (data.type) {
                case "ticket_taken":
                    this.setTicketStatus(data.ticket_id, "taken", "\uD83D\uDC69\u200D\uD83C\uDF73", data.cook_label + " \u0433\u043E\u0442\u0443\u0454");
                    this.updateProgress("in_progress");
                    break;
                case "ticket_done":
                    this.setTicketStatus(data.ticket_id, "done", "\u2705", "\u0413\u043E\u0442\u043E\u0432\u043E");
                    break;
                case "dish_collecting":
                    this.setTicketStatus(data.ticket_id, "collecting", "\uD83C\uDFC3", data.waiter_label);
                    break;
                case "order_accepted":
                    this.updateProgress("accepted");
                    this.showGlobalMessage("\uD83D\uDC4D " + (data.waiter_label || ""));
                    break;
                case "order_verified":
                    this.updateProgress("verified");
                    break;
                case "order_ready":
                    this.updateProgress("ready");
                    this.showGlobalMessage("\uD83C\uDF89 \u0412\u0441\u0456 \u0441\u0442\u0440\u0430\u0432\u0438 \u0433\u043E\u0442\u043E\u0432\u0456!");
                    break;
                case "dish_delivered":
                    this.setTicketStatus(data.ticket_id, "delivered", "\u2705", data.waiter_label || "");
                    break;
                case "order_delivered":
                    this.updateProgress("delivered");
                    this.showGlobalMessage("\u2705 \u0417\u0430\u043C\u043E\u0432\u043B\u0435\u043D\u043D\u044F \u0434\u043E\u0441\u0442\u0430\u0432\u043B\u0435\u043D\u043E! \u0421\u043C\u0430\u0447\u043D\u043E\u0433\u043E!");
                    break;
                case "order_paid":
                    this.showGlobalMessage("\u2705 \u041E\u043F\u043B\u0430\u0442\u0443 \u043F\u0440\u0438\u0439\u043D\u044F\u0442\u043E. \u0414\u044F\u043A\u0443\u0454\u043C\u043E!");
                    this.disconnect();
                    break;
                case "escalation_created":
                    this.showGlobalMessage("\u26A0\uFE0F \u0412\u0430\u0448\u0435 \u0437\u0432\u0435\u0440\u043D\u0435\u043D\u043D\u044F \u043F\u0440\u0438\u0439\u043D\u044F\u0442\u043E");
                    break;
                case "escalation_acknowledged":
                    this.showGlobalMessage("\uD83D\uDC4D " + (data.by || "") + " \u043F\u0440\u0430\u0446\u044E\u0454 \u043D\u0430\u0434 \u0432\u0430\u0448\u0438\u043C \u043F\u0438\u0442\u0430\u043D\u043D\u044F\u043C");
                    break;
                case "escalation_resolved":
                    this.showGlobalMessage("\u2705 " + (data.note || "\u0412\u0438\u0440\u0456\u0448\u0435\u043D\u043E"));
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
            if (!bar) return;
            const targetStep = STATUS_TO_STEP[newStatus];
            if (targetStep === undefined) return;

            bar.querySelectorAll(".progress-step").forEach((step) => {
                const idx = parseInt(step.dataset.stepIndex, 10);
                step.classList.remove("done", "active");
                if (idx <= targetStep) step.classList.add("done");
                if (idx === targetStep) step.classList.add("active");
            });
        }

        showGlobalMessage(text) {
            const el = document.getElementById("order-global-status");
            if (!el) return;
            el.textContent = text;
            el.classList.remove("d-none");
        }

        disconnect() {
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
            window.orderTracker = new OrderTracker(orderId, sseUrl);
        }
    });
})();
