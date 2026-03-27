/**
 * TerminalLog — typewriter-style event log for order tracking.
 *
 * Supports two input formats:
 *   - String: "2026-03-16 17:34:22 — message" (legacy)
 *   - Object: {ts: "...", text: "...", msg_class: "msg-created"} (i18n)
 *
 * For SSE real-time events, uses _eventCatalog + _roleCatalog
 * (injected from Django template) to translate message_key + params.
 */
(function () {
    "use strict";

    function TerminalLog(container, options) {
        options = options || {};
        this.container = container;
        this.charDelay = options.charDelay || 25;
        this.lineDelay = options.lineDelay || 400;
        this.queue = [];
        this.typing = false;
        this.cursor = null;
    }

    /**
     * Add a line to the terminal log.
     * @param {string|object} data - Either "ts — msg" string or {ts, text, msg_class}
     * @param {boolean} instant - If true, skip typewriter animation
     */
    TerminalLog.prototype.addLine = function (data, instant) {
        var parsed = this._parseInput(data);
        var displayText = parsed.ts ? parsed.ts + " — " + parsed.text : parsed.text;

        console.log("[Terminal] addLine instant=" + !!instant + " text=" + displayText.substring(0, 80));
        if (instant) {
            this._appendLine(displayText, parsed.msg_class);
        } else {
            this.queue.push({text: displayText, msg_class: parsed.msg_class});
            if (!this.typing) {
                this._processQueue();
            }
        }
    };

    /**
     * Parse input into {ts, text, msg_class}.
     */
    TerminalLog.prototype._parseInput = function (data) {
        if (typeof data === "object" && data !== null) {
            return {
                ts: data.ts || "",
                text: data.text || "",
                msg_class: data.msg_class || "",
            };
        }
        // Legacy string: "YYYY-MM-DD HH:MM:SS — message"
        var match = String(data).match(/^(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})\s—\s(.*)$/);
        if (match) {
            return {ts: match[1], text: match[2], msg_class: ""};
        }
        return {ts: "", text: String(data), msg_class: ""};
    };

    TerminalLog.prototype._appendLine = function (text, msgClass) {
        var line = document.createElement("div");
        line.className = "terminal-line";
        line.innerHTML = this._formatLine(text, msgClass);
        this.container.appendChild(line);
        this._scrollToBottom();
    };

    TerminalLog.prototype._formatLine = function (text, msgClass) {
        var match = text.match(/^(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})\s—\s(.*)$/);
        if (match) {
            var cls = msgClass || this._detectMsgClass(match[2]);
            return (
                '<span class="ts">' + this._escapeHtml(match[1]) + "</span> — " +
                '<span class="msg ' + cls + '">' + this._escapeHtml(match[2]) + "</span>"
            );
        }
        return '<span class="msg">' + this._escapeHtml(text) + "</span>";
    };

    TerminalLog.prototype._detectMsgClass = function (msg) {
        // Fallback keyword detection for legacy events without msg_class.
        var lower = msg.toLowerCase();
        if (lower.indexOf("submitted") !== -1 || lower.indexOf("сформовано") !== -1) return "msg-created";
        if (lower.indexOf("verified") !== -1 || lower.indexOf("перевірив") !== -1) return "msg-approved";
        if (lower.indexOf("kitchen") !== -1 && lower.indexOf("started") !== -1) return "msg-kitchen";
        if (lower.indexOf("prepared") !== -1 || lower.indexOf("приготував") !== -1 || lower.indexOf("✅") !== -1) return "msg-done";
        if (lower.indexOf("all dishes ready") !== -1 || lower.indexOf("усі страви готові") !== -1) return "msg-ready";
        if (lower.indexOf("delivered") !== -1 || lower.indexOf("доставив") !== -1) return "msg-delivered";
        if (lower.indexOf("payment") !== -1 || lower.indexOf("оплат") !== -1) return "msg-paid";
        if (lower.indexOf("cancelled") !== -1 || lower.indexOf("скасовано") !== -1) return "msg-cancelled";
        return "";
    };

    TerminalLog.prototype._escapeHtml = function (text) {
        var div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    };

    TerminalLog.prototype._processQueue = function () {
        var self = this;
        self.typing = true;

        function next() {
            if (self.queue.length === 0) {
                self.typing = false;
                self._removeCursor();
                return;
            }
            var item = self.queue.shift();
            self._typeLine(item.text, item.msg_class, function () {
                setTimeout(next, self.lineDelay);
            });
        }

        next();
    };

    TerminalLog.prototype._typeLine = function (text, msgClass, callback) {
        var self = this;
        var line = document.createElement("div");
        line.className = "terminal-line";
        this.container.appendChild(line);

        var match = text.match(/^(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})\s—\s(.*)$/);
        var tsText = match ? match[1] : "";
        var separator = match ? " — " : "";
        var msgText = match ? match[2] : text;
        var fullText = tsText + separator + msgText;

        var tsSpan = document.createElement("span");
        tsSpan.className = "ts";
        var cls = msgClass || (match ? self._detectMsgClass(match[2]) : "");
        var msgSpan = document.createElement("span");
        msgSpan.className = "msg" + (cls ? " " + cls : "");
        line.appendChild(tsSpan);

        var charIndex = 0;
        var tsLen = tsText.length;
        var sepLen = separator.length;

        self._addCursor(line);

        function typeChar() {
            if (charIndex < fullText.length) {
                var ch = fullText[charIndex];
                if (charIndex < tsLen) {
                    tsSpan.textContent += ch;
                } else if (charIndex < tsLen + sepLen) {
                    if (charIndex === tsLen) {
                        var sepNode = document.createTextNode(separator);
                        line.insertBefore(sepNode, self.cursor);
                        line.insertBefore(msgSpan, self.cursor);
                        charIndex = tsLen + sepLen - 1;
                    }
                } else {
                    msgSpan.textContent += ch;
                }

                charIndex++;
                self._scrollToBottom();
                var delay = self.charDelay + Math.random() * 15 - 7;
                setTimeout(typeChar, delay);
            } else {
                self._removeCursor();
                callback();
            }
        }

        typeChar();
    };

    TerminalLog.prototype._addCursor = function (parent) {
        this._removeCursor();
        this.cursor = document.createElement("span");
        this.cursor.className = "terminal-cursor";
        parent.appendChild(this.cursor);
    };

    TerminalLog.prototype._removeCursor = function () {
        if (this.cursor && this.cursor.parentNode) {
            this.cursor.parentNode.removeChild(this.cursor);
        }
        this.cursor = null;
    };

    TerminalLog.prototype._scrollToBottom = function () {
        this.container.scrollTop = this.container.scrollHeight;
    };

    // --- SSE message formatting ---

    /**
     * Format an SSE event using _eventCatalog and _roleCatalog.
     * Falls back to log_line if catalog is unavailable.
     */
    function formatSSEEvent(data) {
        if (!data.message_key || !window._eventCatalog) {
            return {
                text: data.log_line || "",
                msg_class: data.msg_class || "",
                ts: data.timestamp || "",
            };
        }

        var template = window._eventCatalog[data.message_key] || data.message_key;
        var params = data.params || {};

        // Resolve staff_label from role + name.
        if (params.staff_role && !params.staff_label) {
            var title = params.staff_display_title || "";
            if (!title && window._roleCatalog) {
                title = window._roleCatalog[params.staff_role] || params.staff_role;
            }
            var name = params.staff_name || "";
            params.staff_label = (title + " " + name).trim();
        }

        // Interpolate %(name)s placeholders.
        var text = template.replace(/%\((\w+)\)s/g, function (m, key) {
            return params[key] !== undefined ? params[key] : m;
        });

        return {
            text: text,
            msg_class: data.msg_class || "",
            ts: data.timestamp || "",
        };
    }

    // Export
    window.TerminalLog = TerminalLog;
    window.formatSSEEvent = formatSSEEvent;
})();
