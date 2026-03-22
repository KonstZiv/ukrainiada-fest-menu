/**
 * TerminalLog — typewriter-style event log for order tracking.
 *
 * Usage:
 *   var term = new TerminalLog(document.getElementById("terminal"), {
 *       charDelay: 25,   // ms per character (typewriter speed)
 *       lineDelay: 400,  // ms pause between lines
 *   });
 *   term.addLine("2026-03-16 17:34:22 — замовлення сформовано", true);  // instant
 *   term.addLine("2026-03-16 17:36:01 — офіціант прийняв");             // typewriter
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

    TerminalLog.prototype.addLine = function (text, instant) {
        console.log("[Terminal] addLine instant=" + !!instant + " text=" + text.substring(0, 80));
        if (instant) {
            this._appendLine(text);
        } else {
            this.queue.push(text);
            if (!this.typing) {
                this._processQueue();
            }
        }
    };

    TerminalLog.prototype._appendLine = function (text) {
        var line = document.createElement("div");
        line.className = "terminal-line";
        line.innerHTML = this._formatLine(text);
        this.container.appendChild(line);
        this._scrollToBottom();
    };

    TerminalLog.prototype._formatLine = function (text) {
        // Split "YYYY-MM-DD HH:MM:SS — message" into timestamp + message
        var match = text.match(/^(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})\s—\s(.*)$/);
        if (match) {
            var msgClass = this._detectMsgClass(match[2]);
            return (
                '<span class="ts">' + this._escapeHtml(match[1]) + "</span> — " +
                '<span class="msg ' + msgClass + '">' + this._escapeHtml(match[2]) + "</span>"
            );
        }
        return '<span class="msg">' + this._escapeHtml(text) + "</span>";
    };

    TerminalLog.prototype._detectMsgClass = function (msg) {
        var lower = msg.toLowerCase();
        if (lower.indexOf("сформовано") !== -1) return "msg-created";
        if (lower.indexOf("перевірив") !== -1 || lower.indexOf("передав") !== -1) return "msg-approved";
        if (lower.indexOf("кухня:") !== -1 && lower.indexOf("прийняв") !== -1) return "msg-kitchen";
        if (lower.indexOf("приготував") !== -1 || lower.indexOf("✅") !== -1) return "msg-done";
        if (lower.indexOf("усі страви готові") !== -1) return "msg-ready";
        if (lower.indexOf("доставив") !== -1) return "msg-delivered";
        if (lower.indexOf("оплат") !== -1) return "msg-paid";
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
            var text = self.queue.shift();
            self._typeLine(text, function () {
                setTimeout(next, self.lineDelay);
            });
        }

        next();
    };

    TerminalLog.prototype._typeLine = function (text, callback) {
        var self = this;
        var line = document.createElement("div");
        line.className = "terminal-line";
        this.container.appendChild(line);

        // Parse into ts + msg parts for coloring
        var match = text.match(/^(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})\s—\s(.*)$/);
        var tsText = match ? match[1] : "";
        var separator = match ? " — " : "";
        var msgText = match ? match[2] : text;
        var fullText = tsText + separator + msgText;

        var tsSpan = document.createElement("span");
        tsSpan.className = "ts";
        var msgClass = match ? self._detectMsgClass(match[2]) : "";
        var msgSpan = document.createElement("span");
        msgSpan.className = "msg" + (msgClass ? " " + msgClass : "");
        line.appendChild(tsSpan);

        var charIndex = 0;
        var tsLen = tsText.length;
        var sepLen = separator.length;

        // Add blinking cursor
        self._addCursor(line);

        function typeChar() {
            if (charIndex < fullText.length) {
                var ch = fullText[charIndex];
                if (charIndex < tsLen) {
                    tsSpan.textContent += ch;
                } else if (charIndex < tsLen + sepLen) {
                    // Separator " — " — append directly to line as text
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

                // Vary speed slightly for natural feel
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

    // Export
    window.TerminalLog = TerminalLog;
})();
