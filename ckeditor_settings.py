# Настройки CKEditor для добавления в settings.py

INSTALLED_APPS_CKEDITOR = [
    'ckeditor',
    'ckeditor_uploader',
]

CKEDITOR_CONFIGS = {
    'default': {
        'toolbar': 'full',
        'height': 400,
        'width': '100%',
        'toolbar_Custom': [
            ['Bold', 'Italic', 'Underline', 'Strike'],
            ['NumberedList', 'BulletedList', '-', 'Outdent', 'Indent', '-', 'JustifyLeft', 'JustifyCenter', 'JustifyRight', 'JustifyBlock'],
            ['Link', 'Unlink', 'Anchor'],
            ['Image', 'Table', 'HorizontalRule', 'SpecialChar'],
            ['Format', 'Font', 'FontSize'],
            ['TextColor', 'BGColor'],
            ['Undo', 'Redo'],
            ['Source'],
        ],
        'extraPlugins': ','.join([
            'uploadimage',
            'image2',
            'codesnippet',
        ]),
    }
}

CKEDITOR_UPLOAD_PATH = "uploads/"
CKEDITOR_IMAGE_BACKEND = "pillow"
CKEDITOR_JQUERY_URL = 'https://ajax.googleapis.com/ajax/libs/jquery/2.2.4/jquery.min.js'
CKEDITOR_ALLOW_NONIMAGE_FILES = False
