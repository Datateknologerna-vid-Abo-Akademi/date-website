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
// A room without a daily window can also take a booking that runs into the next
// day or over several days. Both are offered only for such a room, because a room
// with bookable hours refuses both on the server, and an option that can only
// fail is worse than no option. The multi day one stays behind a single link
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

    // The two longer options, only for a room that can take them.
    var overnightBox = null;
    var toggle = null;
    var endGroup = null;
    var endDateInput = null;

    if (row.dataset.bookingLonger === "1") {
        var extras = document.createElement("span");
        extras.className = "booking-when-extras";

        var overnightLabel = document.createElement("label");
        overnightLabel.className = "booking-when-option";
        overnightBox = document.createElement("input");
        overnightBox.type = "checkbox";
        overnightLabel.append(
            overnightBox,
            document.createTextNode(row.dataset.bookingRangeOvernightLabel || "Slutar nästa dag"),
        );

        toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "booking-when-toggle";
        toggle.setAttribute("aria-pressed", "false");
        toggle.textContent = row.dataset.bookingRangeMultiDayLabel || "Flera dagar";

        extras.append(overnightLabel, toggle);
        group.after(extras);

        endGroup = document.createElement("span");
        endGroup.className = "booking-when-end";
        endGroup.hidden = true;

        endDateInput = document.createElement("input");
        endDateInput.type = "date";
        endDateInput.id = (row.id || "booking-when") + "-end-date";
        endDateInput.className = "booking-when-end-date";

        var endLabel = document.createElement("label");
        endLabel.htmlFor = endDateInput.id;
        endLabel.textContent = row.dataset.bookingRangeEndDateLabel || "Till datum";

        endGroup.append(endLabel, endDateInput);
        extras.after(endGroup);
    }

    function multiDay() {
        return Boolean(endGroup) && !endGroup.hidden;
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
            if (multiDay() && !endDateInput.value) {
                endDateInput.value = day || "";
            }
            if (day && endDateInput.value && endDateInput.value < day) {
                endDateInput.value = day;
            }
        }
    }

    if (toggle) {
        toggle.addEventListener("click", function () {
            var open = toggle.getAttribute("aria-pressed") !== "true";
            toggle.setAttribute("aria-pressed", String(open));
            toggle.classList.toggle("booking-when-toggle-on", open);
            endGroup.hidden = !open;
            overnightBox.parentElement.hidden = open;
            if (open && (!endDateInput.value || endDateInput.value === dateInput.value)) {
                // Opened with the two clocks already set the same day: the same
                // day cannot hold an end before the start, so the end date starts
                // on the next day and the visitor moves it from there.
                if (fromInput.value && toInput.value && toInput.value < fromInput.value) {
                    endDateInput.value = bookingAddDays(dateInput.value, 1);
                } else if (!endDateInput.value) {
                    endDateInput.value = dateInput.value || "";
                }
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
    if (existingEnd[0] && existingStart[0] && existingEnd[0] !== existingStart[0] && endGroup) {
        if (existingEnd[0] === bookingAddDays(existingStart[0], 1) && overnightBox) {
            overnightBox.checked = true;
        } else {
            toggle.setAttribute("aria-pressed", "true");
            toggle.classList.add("booking-when-toggle-on");
            endGroup.hidden = false;
            overnightBox.parentElement.hidden = true;
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
