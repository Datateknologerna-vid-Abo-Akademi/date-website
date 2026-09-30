from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

from core.utils import validate_captcha

from .forms import PostForm
from .models import Post

MAX_POSTS = 100


def index(request):
    form = PostForm()
    if request.method == 'POST':
        form = PostForm(request.POST)
        if form.is_valid():
            if validate_captcha(request.POST.get('cf-turnstile-response', '')):
                form.save()
                messages.success(request, _('Ditt inlägg har lagts till!'))
                return redirect('klotterplanket:index')
            messages.error(request, _('Botkontrollen misslyckades, försök igen.'))
        else:
            messages.error(request, _('Kontrollera pseudonymen och meddelandet.'))

    posts = Post.objects.all()[:MAX_POSTS]
    return render(request, 'klotterplanket/index.html', {'form': form, 'posts': posts})
