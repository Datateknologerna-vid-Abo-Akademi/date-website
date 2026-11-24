/* Hide the choices controls when the question does not use them. Keep the
   table cell in stock admin so the columns still line up. */
(function () {
    var TYPE_SELECTOR = '#eventregistrationform_set-group select[name$="-type"]';

    function sync(type) {
        var stacked = type.closest('[data-inline-type="stacked"]');
        var block = type.closest(stacked ? '.form-group' : 'tr');
        var choices = block && block.querySelector(stacked ? '.field-choice_list' : '.choice-list-widget');
        if (choices) {
            choices.hidden = type.value !== 'select';
        }
    }

    function syncAll() {
        document.querySelectorAll(TYPE_SELECTOR).forEach(sync);
    }

    document.addEventListener('change', function (event) {
        if (event.target.matches(TYPE_SELECTOR)) {
            sync(event.target);
        }
    });

    document.addEventListener('formset:added', function () {
        window.setTimeout(syncAll, 0);
    });

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', syncAll);
    } else {
        syncAll();
    }
})();
