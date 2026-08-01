function initFlatpickrFields(root) {
    if (typeof flatpickr === "undefined") {
        return;
    }

    root = root || document;

    root.querySelectorAll(".flatpickr-date").forEach(function (el) {
        if (el._flatpickr) {
            return;
        }
        flatpickr(el, {
            dateFormat: "Y-m-d",
            allowInput: true,
            locale: { firstDayOfWeek: 1 },
        });
    });

    root.querySelectorAll(".flatpickr-datetime").forEach(function (el) {
        if (el._flatpickr) {
            return;
        }
        flatpickr(el, {
            enableTime: true,
            dateFormat: "Y-m-d H:i",
            altInput: true,
            altFormat: "Y-m-d H:i",
            time_24hr: true,
            allowInput: true,
            locale: { firstDayOfWeek: 1 },
        });
    });

    root.querySelectorAll("[data-clear-datetime]").forEach(function (button) {
        if (button.dataset.clearDatetimeReady === "true") {
            return;
        }
        button.dataset.clearDatetimeReady = "true";
        button.addEventListener("click", function () {
            var input = document.querySelector(button.dataset.clearDatetime);
            if (!input) {
                return;
            }
            if (input._flatpickr) {
                input._flatpickr.clear();
            } else {
                input.value = "";
            }
            input.dispatchEvent(new Event("change", { bubbles: true }));
            input.focus();
        });
    });

    root.querySelectorAll("[data-set-datetime]").forEach(function (button) {
        if (button.dataset.setDatetimeReady === "true") {
            return;
        }
        button.dataset.setDatetimeReady = "true";
        button.addEventListener("click", function () {
            var input = document.querySelector(button.dataset.setDatetime);
            if (!input) {
                return;
            }
            var value = button.dataset.setDatetimeValue || "";
            if (input._flatpickr) {
                input._flatpickr.setDate(value, true);
            } else {
                input.value = value;
            }
            input.dispatchEvent(new Event("change", { bubbles: true }));
            input.focus();
        });
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
        initFlatpickrFields();
    });
} else {
    initFlatpickrFields();
}
