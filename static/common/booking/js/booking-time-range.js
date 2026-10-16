// Pick the booking's start and end in one field.
//
// The form posts two datetime-local inputs, `start` and `end`, and that pair is
// what the server validates: nothing here changes what is submitted, only what
// the visitor sees. When flatpickr is available the pair is hidden and a single
// range field takes its place, showing both ends at once. When it is not, the
// pair is left exactly as the template rendered it, so a visitor without this
// script still books in two steps.
//
// Two details are deliberate:
//
// - The hidden pair stops being `required`. A hidden required input is refused
//   by the browser with a message it has nowhere to show, so an empty range is
//   left for the server, which answers with the same field error it already
//   renders.
// - The submitted values are written from flatpickr's own Date objects, never
//   parsed back out of the visible text, so the field format the form accepts
//   is produced here rather than guessed at.

function bookingRangeValue(date) {
    function pad(number) {
        return (number < 10 ? "0" : "") + number;
    }
    return (
        date.getFullYear() +
        "-" +
        pad(date.getMonth() + 1) +
        "-" +
        pad(date.getDate()) +
        "T" +
        pad(date.getHours()) +
        ":" +
        pad(date.getMinutes())
    );
}

function writeBookingRange(startInput, endInput, dates) {
    var chosen = (dates || []).filter(Boolean).slice(0, 2).map(bookingRangeValue);
    startInput.value = chosen[0] || "";
    endInput.value = chosen[1] || "";
}

// flatpickr's own month and weekday names are English, and the vendored bundle
// carries no translations with it. The page declares its language and the
// browser can name a month in it, so the calendar is built from that rather
// than from a table of translated words in here. The two reference dates are
// fixed: any January gives the twelve month names in order, and 2026-01-04 is
// a Sunday, which is where flatpickr's weekday list starts.
function bookingRangeLocale(separator) {
    var locale = { firstDayOfWeek: 1, rangeSeparator: " " + separator + " " };
    var language = document.documentElement.getAttribute("lang") || "en";
    try {
        var longMonth = new Intl.DateTimeFormat(language, { month: "long" });
        var shortMonth = new Intl.DateTimeFormat(language, { month: "short" });
        var longDay = new Intl.DateTimeFormat(language, { weekday: "long" });
        var shortDay = new Intl.DateTimeFormat(language, { weekday: "short" });
        var months = { longhand: [], shorthand: [] };
        var weekdays = { longhand: [], shorthand: [] };
        for (var month = 0; month < 12; month += 1) {
            var date = new Date(2026, month, 1);
            months.longhand.push(longMonth.format(date));
            months.shorthand.push(shortMonth.format(date));
        }
        for (var day = 0; day < 7; day += 1) {
            var weekday = new Date(2026, 0, 4 + day);
            weekdays.longhand.push(longDay.format(weekday));
            weekdays.shorthand.push(shortDay.format(weekday));
        }
        locale.months = months;
        locale.weekdays = weekdays;
    } catch (error) {
        // An engine without Intl keeps flatpickr's own English names.
    }
    return locale;
}

function initBookingTimeRange(root) {
    if (typeof flatpickr === "undefined") {
        return;
    }

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

        var picker = document.createElement("input");
        picker.type = "text";
        picker.id = row.id ? row.id + "-field" : "booking-time-range";
        picker.className = "booking-when-picker";
        picker.autocomplete = "off";
        picker.readOnly = true;
        picker.placeholder = row.dataset.bookingRangePlaceholder || "";
        fields.after(picker);
        label.htmlFor = picker.id;

        // The words come from the template rather than from a string in here.
        var separator = row.dataset.bookingRangeSeparator || "-";
        var chosen = [startInput.value, endInput.value].filter(Boolean);

        var calendar = flatpickr(picker, {
            mode: "range",
            enableTime: true,
            time_24hr: true,
            minuteIncrement: 15,
            dateFormat: "Y-m-d H:i",
            minDate: startInput.getAttribute("min") || null,
            locale: bookingRangeLocale(separator),
            onChange: function (dates) {
                writeBookingRange(startInput, endInput, dates);
            },
            onClose: function (dates) {
                writeBookingRange(startInput, endInput, dates);
            },
        });

        if (chosen.length) {
            calendar.setDate(chosen, false);
        }
        writeBookingRange(startInput, endInput, calendar.selectedDates);
        row.classList.add("booking-when-enhanced");
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
        initBookingTimeRange();
    });
} else {
    initBookingTimeRange();
}
