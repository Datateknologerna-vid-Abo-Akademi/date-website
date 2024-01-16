from django.forms import widgets

from django.conf import settings


class PrettyJSONWidget(widgets.Textarea):

    def render(self, name, value, attrs=None, **kwargs):
        html = super(PrettyJSONWidget, self).render(name, value, attrs)
        start_as = self.attrs.get('initial', None) or 'raw'

        return f'<div class="jsonwidget" data-initial="{start_as}"><p><button class="parseraw" type="button">Show parsed</button></p>' + html + '<div class="parsed"></div></div>'

    @property
    def media(self):
        extra = '' if settings.DEBUG else '.min'
        return widgets.Media(
            js=(
                'admin/js/vendor/jquery/jquery%s.js' % extra,
                'admin/js/jquery.init.js',
                'prettyjson/prettyjson.js',
            ),
        )
