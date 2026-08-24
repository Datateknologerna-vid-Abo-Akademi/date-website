(function($) {
    $(document).ready(function() {
        function toggleSignupAdminFields(show) {
            const method = show ? 'show' : 'hide';
            $('[class*="form-row field-sign_up_"]')[method]();
            $('.form-row.field-require_registration_terms')[method]();
        }

        if (!$('#id_sign_up').is(':checked')) {
            toggleSignupAdminFields(false);
            $('fieldset.module').find('h2').each((index, element) => {
                if ($(element).text().match("Anmälningsfält")) $(element).parent().hide();
            });
            $('#eventattendees_set-empty').parents('fieldset.module').hide();
        }
        // Delegated (rather than bound directly to the selects present at
        // page load) so this keeps working for registration-question rows
        // added later via the inline formset's "Add another" control.
        // Classic Django admin clones the empty-form row with jQuery
        // (carrying bound handlers with it), but the Unfold admin theme
        // clones it with plain DOM cloneNode, which does NOT carry over
        // jQuery-bound handlers -- a one-time, non-delegated .change()
        // binding silently stops working for new rows under Unfold.
        $(document).on('change', 'select[id$="type"]', function() {
            var rowEdit = $(this).closest('tr').find('input[id$="choice_list"]');
            if( this.value == "select") {
                rowEdit.prop('disabled', false);
            } else {
                rowEdit.prop('disabled', true);
            }
        });
        // Both the classic Django admin and the Unfold admin theme dispatch
        // this event on the newly inserted row, so apply the current
        // (usually blank) type value's enabled/disabled state right away,
        // instead of waiting for the editor to touch the dropdown.
        $(document).on('formset:added', function(e) {
            $(e.target).find('select[id$="type"]').change();
        });
        $('#id_sign_up').change( function() {
            toggleSignupAdminFields($(this).is(':checked'));
            $('fieldset.module').find('h2').each((index, element) => {
                if ($(element).text().match("Anmälningsfält")) $(element).parent().toggle();
            });
            $('#eventattendees_set-empty').parents('fieldset.module').toggle();
        });
        $('select[id$="type"]').change();

        $('p.datetime').find('br').replaceWith("&nbsp;&nbsp;");
    });
})(django.jQuery);
