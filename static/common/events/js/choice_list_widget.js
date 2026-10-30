/* One input per choice. The hidden count is the number of inputs the server
 * reads, so adding a row only has to bump it; removing a row leaves a gap that
 * the server skips when the value is empty. */
(function () {
    function rowsOf(widget) {
        return widget.querySelector('.choice-list-rows');
    }

    function countOf(widget) {
        return widget.querySelector('input[name$="__count"]');
    }

    function addRow(widget) {
        var count = countOf(widget);
        var index = parseInt(count.value, 10) || 0;
        count.value = String(index + 1);

        var template = widget.querySelector('template.choice-list-row-template');
        var row = template.content.firstElementChild.cloneNode(true);
        var input = row.querySelector('input');
        var prefix = widget.getAttribute('data-choice-list-prefix');
        input.name = prefix + '__choice__' + index;
        input.id = 'id_' + prefix + '_choice_' + index;
        input.value = '';
        rowsOf(widget).appendChild(row);
        input.focus();
    }

    function removeRow(widget, row) {
        if (rowsOf(widget).querySelectorAll('.choice-list-row').length <= 1) {
            row.querySelector('input').value = '';
            return;
        }
        row.remove();
    }

    document.addEventListener('click', function (event) {
        var add = event.target.closest('.choice-list-add');
        if (add) {
            event.preventDefault();
            var widget = add.closest('.choice-list-widget');
            if (widget) {
                addRow(widget);
            }
            return;
        }
        var remove = event.target.closest('.choice-list-remove');
        if (remove) {
            event.preventDefault();
            var row = remove.closest('.choice-list-row');
            var owner = remove.closest('.choice-list-widget');
            if (row && owner) {
                removeRow(owner, row);
            }
        }
    });
})();
