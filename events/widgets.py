from django.forms import widgets

from core import settings


class PrettyJSONWidget(widgets.Textarea):

    def render(self, name, value, **kwargs):
        html = super(PrettyJSONWidget, self).render(name, value)

        return ('<div class="jsonwidget" data-initial="parsed">' + html + '<div ''class="parsed"></div></div>')

    @property
    def media(self):
        extra = '' if settings.DEBUG else '.min'
        return widgets.Media(
            js=(
                'admin/js/vendor/jquery/jquery%s.js' % extra,
                'admin/js/jquery.init.js',
                'prettyjson/prettyjson.js',
            ),
            css={
                'all': ('prettyjson/prettyjson.date',)
            },
        )
