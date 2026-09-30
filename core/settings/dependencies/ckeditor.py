# CKEDITOR 5

customColorPalette = [
    {'color': 'hsl(0, 0%, 0%)', 'label': 'Black'},
    {'color': 'hsl(4, 90%, 58%)', 'label': 'Red'},
    {'color': 'hsl(340, 82%, 52%)', 'label': 'Pink'},
    {'color': 'hsl(291, 64%, 42%)', 'label': 'Purple'},
    {'color': 'hsl(262, 52%, 47%)', 'label': 'Deep Purple'},
    {'color': 'hsl(231, 48%, 48%)', 'label': 'Indigo'},
    {'color': 'hsl(207, 90%, 54%)', 'label': 'Blue'},
]


CKEDITOR_5_CUSTOM_CSS = 'core/css/ckeditor.css'
CKEDITOR_5_FILE_STORAGE = 'core.storage_backends.PublicCKEditorStorage'
CKEDITOR_5_CONFIGS = {
    'default': {
        'toolbar': [
            'heading',
            '|',
            'outdent',
            'indent',
            '|',
            'bold',
            'italic',
            'link',
            'underline',
            'strikethrough',
            'code',
            'subscript',
            'superscript',
            'highlight',
            '|',
            'codeBlock',
            'sourceEditing',
            'insertImage',
            'bulletedList',
            'numberedList',
            'todoList',
            '|',
            'blockQuote',
            'imageUpload',
            '|',
            'fontSize',
            'fontFamily',
            'fontColor',
            'fontBackgroundColor',
            'mediaEmbed',
            'removeFormat',
            'insertTable',
        ],
        'image': {
            'toolbar': [
                'imageTextAlternative',
                '|',
                'imageStyle:alignLeft',
                'imageStyle:alignRight',
                'imageStyle:alignCenter',
                'imageStyle:side',
                '|',
                'imageStyle:noHoverLink',
            ],
            'styles': {
                'options': [
                    'block',
                    'side',
                    'alignLeft',
                    'alignRight',
                    'alignCenter',
                    {
                        'name': 'noHoverLink',
                        'title': 'No hover effect (linked images)',
                        'icon': (
                            '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
                            '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zM4 12c0-4.42 '
                            '3.58-8 8-8 1.85 0 3.55.63 4.9 1.69L5.69 16.9C4.63 15.55 4 13.85 4 12zm8 8c-1.85 '
                            '0-3.55-.63-4.9-1.69L18.31 7.1C19.37 8.45 20 10.15 20 12c0 4.42-3.58 8-8 8z"/>'
                            '</svg>'
                        ),
                        'modelElements': ['imageBlock', 'imageInline'],
                        'className': 'editor-img-no-hover',
                    },
                ],
            },
        },
        'table': {
            'contentToolbar': ['tableColumn', 'tableRow', 'mergeTableCells', 'tableProperties', 'tableCellProperties'],
            'tableProperties': {'borderColors': customColorPalette, 'backgroundColors': customColorPalette},
            'tableCellProperties': {'borderColors': customColorPalette, 'backgroundColors': customColorPalette},
        },
        'heading': {
            'options': [
                {'model': 'paragraph', 'title': 'Paragraph', 'class': 'ck-heading_paragraph'},
                {'model': 'heading1', 'view': 'h1', 'title': 'Heading 1', 'class': 'ck-heading_heading1'},
                {'model': 'heading2', 'view': 'h2', 'title': 'Heading 2', 'class': 'ck-heading_heading2'},
                {'model': 'heading3', 'view': 'h3', 'title': 'Heading 3', 'class': 'ck-heading_heading3'},
            ]
        },
    },
    'list': {
        'properties': {
            'styles': 'true',
            'startIndex': 'true',
            'reversed': 'true',
        }
    },
}
