(function () {
    "use strict";

    function isValidInternalUrl(url) {
        if (typeof url !== "string" || !url) {
            return false;
        }

        var trimmedUrl = url.trim();
        if (trimmedUrl.startsWith("//")) {
            return false;
        }

        var lowerUrl = trimmedUrl.toLowerCase();
        if (lowerUrl.startsWith("javascript:") || lowerUrl.startsWith("data:") || lowerUrl.startsWith("vbscript:")) {
            return false;
        }

        if (trimmedUrl.startsWith("/") && !trimmedUrl.startsWith("//")) {
            return true;
        }

        try {
            var urlObj = new URL(trimmedUrl, window.location.origin);
            return urlObj.origin === window.location.origin;
        } catch (_error) {
            return false;
        }
    }

    function addPopupHtml(eventsJson) {
        Object.entries(eventsJson).forEach(function (entry) {
            var eventData = entry[1];
            var tempDate = new Date(eventData.eventFullDate);
            var hours = tempDate.getHours();
            var minutes = tempDate.getMinutes();

            var safeHours = hours < 10 ? "0" + hours : String(hours);
            var safeMinutes = minutes < 10 ? "0" + minutes : String(minutes);
            var rawUrl = (eventData.link || "").trim();

            var link = document.createElement("a");
            link.className = "calendar-eventday-popup";
            link.id = "calendar_link";

            if (isValidInternalUrl(rawUrl)) {
                try {
                    var urlObj = new URL(rawUrl, window.location.origin);
                    link.href = urlObj.origin === window.location.origin ? urlObj.href : "#";
                } catch (_error) {
                    link.href = "#";
                }
            } else {
                link.href = "#";
            }

            link.appendChild(document.createTextNode(safeHours + ":" + safeMinutes));
            link.appendChild(document.createElement("br"));
            link.appendChild(document.createTextNode(eventData.eventTitle));

            eventData.html = link.outerHTML;
        });
    }

    function initCalendar(eventsJson) {
        if (typeof window.VanillaCalendar !== "function") {
            return;
        }

        document.querySelectorAll(".calendar").forEach(function (calendarElement) {
            var calendarPopups = new window.VanillaCalendar(calendarElement, {
                actions: {
                    clickDay: function (_event, date) {
                        var selectedDate = date[0];
                        if (eventsJson[selectedDate] === undefined) {
                            return;
                        }

                        var rawUrl = (eventsJson[selectedDate].link || "").trim();
                        if (!isValidInternalUrl(rawUrl)) {
                            return;
                        }

                        try {
                            var safeUrl = new URL(rawUrl, window.location.origin);
                            if (safeUrl.origin === window.location.origin) {
                                window.location.href = safeUrl.href;
                            }
                        } catch (_error) {
                            return;
                        }
                    },
                },
                settings: {
                    visibility: {
                        weekend: false,
                    },
                    selected: {
                        month: new Date().getMonth(),
                        year: new Date().getFullYear(),
                    },
                },
                popups: eventsJson,
            });

            calendarPopups.init();
        });
    }

    var calendarScript = document.querySelector("script#calendar_json");
    var eventsJson = {};
    if (calendarScript && calendarScript.textContent) {
        try {
            eventsJson = JSON.parse(calendarScript.textContent);
        } catch (_error) {
            eventsJson = {};
        }
    }

    addPopupHtml(eventsJson);
    initCalendar(eventsJson);
}());
