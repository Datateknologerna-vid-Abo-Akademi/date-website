// Ask for the booking's start and end as a date and two clock times.
//
// The form posts two datetime-local inputs, `start` and `end`, and that pair is
// what the server validates: nothing here changes what is submitted, only what
// the visitor sees. This script hides the pair and shows a date plus two clocks
// instead, arranged as two pairs: the start is a day and a clock, the end is a
// clock, or a day and a clock when the booking runs past midnight. Each pair
// wraps and stays together, so the end never ends up as a day on one line and a
// clock on another.
//
// One date is asked for, because a room booking usually happens on one day, and
// the second one only appears when the visitor asks for a booking over several
// days. Nothing is pre-filled, so no time is chosen for the visitor.
//
// A room without a daily window can also take a booking that runs into the next
// day or over several days. Both are offered only for such a room, because a room
// with bookable hours refuses both on the server, and an option that can only
// fail is worse than no option. The multi day one stays behind a single checkbox
// until it is wanted.
//
// Two details are deliberate:
//
// - The hidden pair stops being `required`. A hidden required input is refused
//   by the browser with a message it has nowhere to show, so a half-filled row
//   is left for the server, which answers with the same field error it already
//   renders. The visible controls are required instead, and they can show the
//   browser's own message.
// - The submitted values are composed from what the visitor picked, in the
//   format the form accepts (BOOKING_DATETIME_FORMAT), never by parsing any
//   displayed text.

function bookingAddDays(value, days) {
    var parts = (value || "").split("-");
    if (parts.length !== 3) {
        return "";
    }
    var date = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
    date.setDate(date.getDate() + days);
    function pad(number) {
        return (number < 10 ? "0" : "") + number;
    }
    return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate());
}

function buildBookingTimeControls(row, startInput, endInput, fields, label) {
    var existingStart = startInput.value ? startInput.value.split("T") : [];
    var existingEnd = endInput.value ? endInput.value.split("T") : [];

    var group = document.createElement("span");
    group.className = "booking-when-split";

    // The start is one pair, the end is another: wrapping the row then keeps each
    // end's day and clock on the same line.
    var fromPair = document.createElement("span");
    fromPair.className = "booking-when-from-pair";

    var tillPair = document.createElement("span");
    tillPair.className = "booking-when-till-pair";

    var dateInput = document.createElement("input");
    dateInput.type = "date";
    dateInput.className = "booking-when-date";
    dateInput.id = (row.id || "booking-when") + "-date";
    dateInput.required = true;
    dateInput.setAttribute("aria-label", row.dataset.bookingRangeDateLabel || "Datum");
    // The earliest day the server accepts, taken from the input it replaced.
    dateInput.min = (startInput.getAttribute("min") || "").split("T")[0] || "";

    var fromInput = document.createElement("input");
    fromInput.type = "time";
    fromInput.className = "booking-when-clock";
    fromInput.id = (row.id || "booking-when") + "-from";
    fromInput.required = true;
    fromInput.setAttribute("aria-label", startInput.getAttribute("aria-label") || "Starttid");

    var toInput = document.createElement("input");
    toInput.type = "time";
    toInput.className = "booking-when-clock";
    toInput.id = (row.id || "booking-when") + "-to";
    toInput.required = true;
    toInput.setAttribute("aria-label", endInput.getAttribute("aria-label") || "Sluttid");

    var between = document.createElement("span");
    between.className = "booking-when-sep";
    between.textContent = row.dataset.bookingRangeSeparator || "till";

    // The two longer options, only for a room that can take them.
    var longer = row.dataset.bookingLonger === "1";
    var endDateInput = null;
    if (longer) {
        endDateInput = document.createElement("input");
        endDateInput.type = "date";
        endDateInput.className = "booking-when-end-date";
        endDateInput.id = (row.id || "booking-when") + "-end-date";
        endDateInput.hidden = true;
        endDateInput.setAttribute("aria-label", row.dataset.bookingRangeEndDateLabel || "Till datum");
    }

    fromPair.append(dateInput, fromInput);
    tillPair.append(toInput);
    if (endDateInput) {
        // The end's own day goes first in its pair, so the pair reads
        // "till [day] [clock]" and keeps the day beside the clock either way.
        tillPair.prepend(endDateInput);
    }
    group.append(fromPair, between, tillPair);
    fields.after(group);
    label.htmlFor = dateInput.id;

    var overnightBox = null;
    var overnightLabel = null;
    var multiBox = null;

    if (longer) {
        var extras = document.createElement("span");
        extras.className = "booking-when-extras";

        overnightLabel = document.createElement("label");
        overnightLabel.className = "booking-when-option";
        overnightBox = document.createElement("input");
        overnightBox.type = "checkbox";
        overnightLabel.append(
            overnightBox,
            document.createTextNode(row.dataset.bookingRangeOvernightLabel || "Slutar nästa dag"),
        );

        var multiLabel = document.createElement("label");
        multiLabel.className = "booking-when-option";
        multiBox = document.createElement("input");
        multiBox.type = "checkbox";
        multiLabel.append(multiBox, document.createTextNode(row.dataset.bookingRangeMultiDayLabel || "Flera dagar"));

        extras.append(overnightLabel, multiLabel);
        group.after(extras);
    }

    function multiDay() {
        return Boolean(multiBox) && multiBox.checked;
    }

    function overnight() {
        return Boolean(overnightBox) && overnightBox.checked && !multiDay();
    }

    function compose() {
        var day = dateInput.value;
        var from = fromInput.value;
        var to = toInput.value;
        startInput.value = day && from ? day + "T" + from : "";

        var endDay = day;
        if (multiDay()) {
            endDay = endDateInput.value || day;
        } else if (overnight() && day) {
            endDay = bookingAddDays(day, 1);
        }
        endInput.value = endDay && to ? endDay + "T" + to : "";

        // An end before the start is only possible while both share a day, so the
        // clock is only constrained then. The server still measures the span and
        // the week limit for the other two.
        toInput.min = multiDay() || overnight() ? "" : from || "";
        if (endDateInput) {
            endDateInput.required = multiDay();
            endDateInput.min = day || "";
            endDateInput.max = day ? bookingAddDays(day, 7) : "";
        }
    }

    // Opening the second day starts from the day already picked, and moves to the
    // next one when the two clocks already cross midnight.
    function revealEndDay() {
        var day = dateInput.value;
        if (!day) {
            return;
        }
        if (!endDateInput.value || endDateInput.value === day) {
            var crossing = fromInput.value && toInput.value && toInput.value < fromInput.value;
            endDateInput.value = crossing ? bookingAddDays(day, 1) : day;
        } else if (endDateInput.value < day) {
            endDateInput.value = day;
        }
    }

    if (multiBox) {
        multiBox.addEventListener("change", function () {
            var open = multiBox.checked;
            endDateInput.hidden = !open;
            overnightLabel.hidden = open;
            row.classList.toggle("booking-when-long", open);
            if (open) {
                revealEndDay();
            }
            compose();
            if (open) {
                endDateInput.focus();
            }
        });
        overnightBox.addEventListener("change", compose);
    }

    // A page re-rendered after a validation error brings back what was chosen,
    // including a booking that ran past midnight.
    if (existingStart[0]) {
        dateInput.value = existingStart[0];
    }
    if (existingStart[1]) {
        fromInput.value = existingStart[1];
    }
    if (existingEnd[1]) {
        toInput.value = existingEnd[1];
    }
    if (existingEnd[0] && existingStart[0] && existingEnd[0] !== existingStart[0] && endDateInput) {
        if (existingEnd[0] === bookingAddDays(existingStart[0], 1)) {
            overnightBox.checked = true;
        } else {
            multiBox.checked = true;
            endDateInput.hidden = false;
            overnightLabel.hidden = true;
            row.classList.add("booking-when-long");
            endDateInput.value = existingEnd[0];
        }
    }

    [dateInput, fromInput, toInput].forEach(function (input) {
        input.addEventListener("input", compose);
        input.addEventListener("change", compose);
    });
    if (endDateInput) {
        endDateInput.addEventListener("input", compose);
        endDateInput.addEventListener("change", compose);
    }
    compose();
    row.classList.add("booking-when-split-ready");
}

function initBookingTimeRange(root) {
    root = root || document;

    root.querySelectorAll("[data-booking-time-range]").forEach(function (row) {
        if (row.dataset.bookingTimeRangeReady === "true") {
            return;
        }

        var startInput = row.querySelector("input[name='start']");
        var endInput = row.querySelector("input[name='end']");
        var fields = row.querySelector("[data-booking-range-fields]");
        var label = row.querySelector("label");
        if (!startInput || !endInput || !fields || !label) {
            return;
        }
        row.dataset.bookingTimeRangeReady = "true";

        startInput.required = false;
        endInput.required = false;

        buildBookingTimeControls(row, startInput, endInput, fields, label);
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
        initBookingTimeRange();
    });
} else {
    initBookingTimeRange();
}
