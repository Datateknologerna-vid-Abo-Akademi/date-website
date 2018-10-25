(function($) {
    $(document).ready(function() {
        if (!$('#id_sign_up').is(':checked')) {
            $('[class*="form-row field-sign_up_"]').hide()
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
            $('[class*="form-row field-sign_up_"]').toggle()
            $('fieldset.module').find('h2').each((index, element) => {
                if ($(element).text().match("Anmälningsfält")) $(element).parent().toggle();
            });
            $('#eventattendees_set-empty').parents('fieldset.module').toggle();
        });
        $('select[id$="type"]').change();


    });
})(django.jQuery);
