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
        $('select[id$="type"]').change( function() {
            var rowEdit = $($(this).parents('tr')).find('input[id$="choice_list"]');
            if( this.value == "select") {
                rowEdit.prop('disabled', false);
            } else {
                rowEdit.prop('disabled', true);
            }
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
