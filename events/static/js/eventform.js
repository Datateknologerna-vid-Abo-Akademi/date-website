(function($) {
    $(document).ready(function() {
        if (!$('#id_sign_up').is(':checked')) {
            $('[class*="form-row field-sign_up_"]').hide()
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
        });
        $('select[id$="type"]').change();


    });
})(django.jQuery);
