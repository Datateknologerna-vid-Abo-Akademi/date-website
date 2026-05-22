from django import template

from core.admin_ui import get_topbar_quick_create_links

register = template.Library()


@register.simple_tag(takes_context=True)
def admin_topbar_quick_create_links(context):
    return get_topbar_quick_create_links(context['request'])


@register.simple_tag(takes_context=True)
def admin_changelist_extra_links(context, cl):
    model_admin = cl.model_admin
    if not hasattr(model_admin, 'get_changelist_links'):
        return []
    return model_admin.get_changelist_links(context['request'])
