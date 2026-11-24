/* Stock Django uses table headers as labels. Repeat them in the cells so
   each field stays identifiable when its row stacks on a narrow screen. */
(function () {
    var groups = [
        'functionary_set-group', 'photo_set-group', 'examfile_set-group',
        'document_set-group', 'eventregistrationform_set-group',
        'eventattendees_set-group', 'choice_set-group'
    ];

    document.addEventListener('DOMContentLoaded', function () {
        groups.forEach(function (id) {
            var group = document.getElementById(id);
            var table = group && group.querySelector('.tabular > fieldset > .wrapper > table, .tabular > fieldset > details > .wrapper > table');
            if (!table || !table.tHead || !table.tBodies.length) return;

            var columns = Array.from(table.tHead.rows[0].cells);
            Array.from(table.tBodies[0].rows).forEach(function (row) {
                if (!row.classList.contains('form-row')) return;
                Array.from(row.cells).forEach(function (cell, index) {
                    var heading = columns[index];
                    if (!heading || cell.classList.contains('hidden')) return;
                    var text = heading.textContent.trim();
                    if (!text) return;
                    var control = cell.querySelector('input[id]:not([type="hidden"]), select[id], textarea[id]');
                    if (cell.classList.contains('delete') && !control) return;
                    var label = document.createElement(control ? 'label' : 'span');
                    label.className = 'stock-inline-field-label';
                    label.textContent = text;
                    if (control) label.htmlFor = control.id;
                    cell.prepend(label);
                });
            });
            group.classList.add('stock-inline-responsive');
        });
    });
})();
