import django_tables2 as tables

from .models import Document


class DocumentTable(tables.Table):

    class Meta:
        model = Document
        template_name = "django_tables2/bootstrap.html"
        fields = ('collection', 'title', 'document')


class SumColumn(tables.Column):

    def render_footer(self, bound_column, table):
        return sum(bound_column.accessor.reslove(row) for row in table.data)
