# Create your views here.
import datetime
import logging

from django.db.models import Count
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views import generic

from .forms import FlagForm
from .models import Ctf, Flag, Guess, PostMortem

logger = logging.getLogger('date')


class IndexView(generic.ListView):
    template_name = 'ctf/index.html'
    context_object_name = 'latest_ctf_list'

    def get_queryset(self):
        """Return the last five published questions."""
        return Ctf.objects.order_by('-pub_date')[:5]


class DetailView(generic.DetailView):
    model = Ctf
    template_name = 'ctf/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        flags = Flag.objects.filter(ctf=self.object)
        context['flags'] = flags
        return context


def flag(request, ctf_slug, flag_slug):
    ctf = Ctf.objects.filter(slug=ctf_slug).first()
    ctf_flags = Flag.objects.filter(ctf=ctf)
    flag = Flag.objects.filter(ctf=ctf, slug=flag_slug).first()

    form = FlagForm()
    context = {'ctf': ctf, 'flag': flag, 'form': form}

    if request.session.get("flag_valid", False):
        request.session['flag_valid'] = False
        return form_valid(request, context)
    elif request.session.get("flag_invalid", False):
        request.session['flag_invalid'] = False
        return form_invalid(request, context)

    # Check if user has already solved a flag
    user_solved = False
    for ctf_flag in ctf_flags:
        if ctf_flag.solver and request.user == ctf_flag.solver:
            user_solved = True
            context['user_solved'] = user_solved

    if request.method == 'POST':
        if ctf.ctf_is_open() and ctf.published and (request.user.is_authenticated):
            form = FlagForm(request.POST or None)

            if form.is_valid():
                # Check if a input matches the flag
                flag_input = form.cleaned_data.get('flag')
                if flag_input:
                    logger.info(f"FLAG: {flag.title} USER: {request.user} INPUT: {flag_input}")
                    flag_query = Flag.objects.filter(ctf=ctf, slug=flag_slug, flag=flag_input)

                    if flag_query.exists():
                        flag_instance = flag_query.first()
                        request.session['flag_valid'] = True
                        if user_solved or flag_instance.solver or ctf.ctf_ended():
                            # User has already solved a flag or flag is already solved or ctf has ended
                            Guess.objects.create(
                                ctf=ctf, flag=flag_instance, user=request.user, guess=flag_input, correct=True
                            )
                            return redirect(request.path)
                        else:
                            # Flag is correctly guessed for the first time
                            flag_instance.solver = request.user
                            flag_instance.solved_date = datetime.datetime.now()
                            flag_instance.save()
                            logger.info(f"Solver: {flag_instance.solver}")
                            context['flag'] = flag_instance
                            context['solved'] = True
                            Guess.objects.create(
                                ctf=ctf, flag=flag_instance, user=request.user, guess=flag_input, correct=True
                            )
                            return redirect(request.path)
                    else:
                        # Guess was incorrect or flag does not match
                        if flag:  # Ensure flag instance is not None before creating Guess
                            Guess.objects.create(ctf=ctf, flag=flag, user=request.user, guess=flag_input, correct=False)
                        else:
                            # Handle the case where no valid flag instance is available
                            # This could log an error, notify the user, etc., depending on desired behavior
                            logger.error("Attempted to create a guess with an invalid flag instance.")

                request.session['flag_invalid'] = True
                return redirect(request.path)

        return HttpResponseForbidden()
    # render non post request
    return render(request, 'ctf/flag_detail.html', context)


def form_valid(request, context):
    logger.info('VALID FLAG')
    context['valid'] = '🎊🎊🎊 Rätt Flag! 🎊🎊🎊'
    return render(request, 'ctf/flag_detail.html', context)


def form_invalid(request, context):
    logger.info('INVALID FLAG')
    context['invalid'] = 'Fel Flag angiven, prova igen.'
    return render(request, 'ctf/flag_detail.html', context)


class PostMortemIndexView(generic.ListView):
    template_name = 'ctf/post_mortem_index.html'
    context_object_name = 'post_mortems'

    def get_queryset(self):
        return PostMortem.objects.visible().select_related('ctf').order_by('-ctf__start_date')


class PostMortemDetailView(generic.DetailView):
    model = PostMortem
    template_name = 'ctf/post_mortem_detail.html'
    context_object_name = 'post_mortem'

    def get_queryset(self):
        return PostMortem.objects.visible()

    def get_object(self, queryset=None):
        queryset = queryset if queryset is not None else self.get_queryset()
        return get_object_or_404(queryset.select_related('ctf'), ctf__slug=self.kwargs['ctf_slug'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ctf = self.object.ctf
        # Restrict the aggregate to guesses whose flag belongs to this CTF: a
        # Guess row can point at a flag from another CTF, and such a row must
        # not inflate the total.
        input_counts = {
            row['flag_id']: row['inputs']
            for row in Guess.objects.filter(ctf=ctf, flag__ctf=ctf).values('flag_id').annotate(inputs=Count('id'))
        }
        context['ctf'] = ctf
        context['challenges'] = [
            {'flag': flag, 'inputs': input_counts.get(flag.pk, 0)}
            for flag in Flag.objects.filter(ctf=ctf).select_related('solver').order_by('pk')
        ]
        # Total is the sum of the rendered rows, so the data block always adds up.
        context['total_guesses'] = sum(challenge['inputs'] for challenge in context['challenges'])
        return context
