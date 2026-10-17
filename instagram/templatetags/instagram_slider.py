from django import template

register = template.Library()


@register.filter
def conveyor(posts, minimum=16):
    """Return the slider track as ``(post, is_repeat)`` pairs.

    The posts are repeated until each half of the track holds at least
    ``minimum`` images, wide enough to cover the slider, and the track is two
    identical halves so the CSS can loop by moving it exactly half its width.
    Only the first occurrence of each post is marked as not a repeat.
    """
    posts = list(posts)
    if not posts:
        return []
    half = posts * -(-int(minimum) // len(posts))
    return [(post, index >= len(posts)) for index, post in enumerate(half + half)]
