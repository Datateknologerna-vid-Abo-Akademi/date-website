/* The choices list only applies to a Multiple choice field. Hide its row for
   the other types instead of leaving an input whose value the model discards.
   The input stays in the DOM, so the formset payload does not change. */
(function () {
    var GROUP_ID = 'eventregistrationform_set-group';

    function sync(block) {
        var type = block.querySelector('select[name$="-type"]');
        var row = block.querySelector('.field-choice_list');
        if (!type || !row) {
            return;
        }
        row.hidden = type.value !== 'select';
    }

    function syncAll() {
        var group = document.getElementById(GROUP_ID);
        if (!group || !group.matches('[data-inline-type="stacked"]')) {
            return;
        }
        group.querySelectorAll('.form-group').forEach(sync);
    }

    document.addEventListener('change', function (event) {
        var target = event.target;
        if (!target.matches('#eventregistrationform_set-group select[name$="-type"]')) {
            return;
        }
        // The stock admin keeps its table column; only the stacked blocks hide it.
        if (!target.closest('[data-inline-type="stacked"]')) {
            return;
        }
        var block = target.closest('.form-group');
        if (block) {
            sync(block);
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
