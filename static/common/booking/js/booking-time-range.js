// Ask for the booking's start and end as a date and two clock times.
//
// The form posts two datetime-local inputs, `start` and `end`, and that pair is
// what the server validates: nothing here changes what is submitted, only what
// the visitor sees. This script hides the pair and shows a date plus two clocks
// instead. One date, because a room booking happens on one day and the visitor
// should not be asked for it twice; two clocks, because the two ends of that day
// are the only thing that differs. Without the script the pair is left exactly
// as the template rendered it, so a visitor with JavaScript off still books in
// two steps.
//
// Two details are deliberate:
//
// - The hidden pair stops being `required`. A hidden required input is refused
//   by the browser with a message it has nowhere to show, so a half-filled row
//   is left for the server, which answers with the same field error it already
//   renders. The three visible controls are required instead, and they can show
//   the browser's own message.
// - The submitted values are composed from what the visitor picked, in the
//   format the form accepts (BOOKING_DATETIME_FORMAT), never by parsing any
//   displayed text.

function buildBookingTimeControls(row, startInput, endInput, fields, label) {
    var existingStart = startInput.value ? startInput.value.split("T") : [];
    var existingEnd = endInput.value ? endInput.value.split("T") : [];

    var group = document.createElement("span");
    group.className = "booking-when-split";

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

    group.append(dateInput, fromInput, between, toInput);
    fields.after(group);
    label.htmlFor = dateInput.id;

    // A page re-rendered after a validation error brings back what was chosen.
    if (existingStart[0]) {
        dateInput.value = existingStart[0];
    }
    if (existingStart[1]) {
        fromInput.value = existingStart[1];
    }
    if (existingEnd[0] && !dateInput.value) {
        dateInput.value = existingEnd[0];
    }
    if (existingEnd[1]) {
        toInput.value = existingEnd[1];
    }

    function compose() {
        startInput.value =
            dateInput.value && fromInput.value ? dateInput.value + "T" + fromInput.value : "";
        endInput.value = dateInput.value && toInput.value ? dateInput.value + "T" + toInput.value : "";
        // Both ends are on the picked day, so an end before the start is the one
        // mistake this row can still invite; the browser is told the earliest end
        // it may offer.
        toInput.min = fromInput.value || "";
    }

    [dateInput, fromInput, toInput].forEach(function (input) {
        input.addEventListener("input", compose);
        input.addEventListener("change", compose);
    });
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
