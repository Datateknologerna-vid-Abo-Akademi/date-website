import logging
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect, render
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin

from .filters import ExamFilter
from .forms import ExamArchiveUploadForm, ExamBankPasswordForm, ExamUploadForm
from .models import ExamArchive, ExamBankAccessSettings, ExamFile
from .tables import ExamFileTable

logger = logging.getLogger('date')

EXAM_BANK_ACCESS_SESSION_KEY = 'exambank_access_password_hash'


def user_type(user):
    if not user.is_authenticated:
        return False
    return user.membership_type.permission_profile != 3


def exam_bank_access_is_allowed(request, access_settings=None):
    access_settings = access_settings or ExamBankAccessSettings.get_solo()
    if access_settings.require_sign_in:
        return user_type(request.user)
    if not access_settings.has_password:
        return True
    return request.session.get(EXAM_BANK_ACCESS_SESSION_KEY) == access_settings.password_hash


def exam_bank_password_gate(request, access_settings):
    status = 200
    if request.method == 'POST':
        form = ExamBankPasswordForm(request.POST, access_settings=access_settings)
        if form.is_valid():
            request.session[EXAM_BANK_ACCESS_SESSION_KEY] = access_settings.password_hash
            return redirect(request.get_full_path())
        status = 403
    else:
        form = ExamBankPasswordForm(access_settings=access_settings)

    return render(request, 'archive/exam_password.html', {
        'form': form,
    }, status=status)


def exam_bank_access_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        access_settings = ExamBankAccessSettings.get_solo()
        if exam_bank_access_is_allowed(request, access_settings):
            return view_func(request, *args, **kwargs)
        if access_settings.require_sign_in:
            return redirect_to_login(request.get_full_path(), login_url='/members/login/')
        return exam_bank_password_gate(request, access_settings)

    return wrapper


@exam_bank_access_required
def exams_index(request):
    archives = ExamArchive.objects.all().order_by('title')
    return render(request, 'archive/exams_index.html', {
        'type': "exams",
        'collections': archives,
    })


@exam_bank_access_required
def exam_upload(request, pk):
    archive = ExamArchive.objects.filter(pk=pk).first()
    if request.method == 'POST' and archive:
        form = ExamUploadForm(request.POST)
        if form.is_valid():
            if not request.FILES.getlist('exam'):
                return redirect('archive:exams')
            for uploaded_file in request.FILES.getlist('exam'):
                ExamFile.objects.create(document=uploaded_file, title=form.cleaned_data['title'], archive=archive)
            logger.debug(f'User: {request.user} added files to {archive.title}')
        return redirect('archive:exams_detail', archive.pk)

    return render(request, 'archive/exam_upload.html', {
        'collection': archive,
        'exam_form': ExamUploadForm,
    })


@exam_bank_access_required
def exam_archive_upload(request):
    if request.method == 'POST':
        form = ExamArchiveUploadForm(request.POST)
        if form.is_valid():
            ExamArchive.objects.create(title=form.cleaned_data['title'])
            logger.debug(f'User: {request.user} added exams-archive: {form.cleaned_data["title"]}')
        return redirect('archive:exams')

    return render(request, 'archive/exam_upload.html', {
        'exam_form': ExamArchiveUploadForm,
    })


class FilteredExamsListView(SingleTableMixin, FilterView):
    model = ExamFile
    paginate_by = 15
    table_class = ExamFileTable
    template_name = 'archive/exam_detail.html'
    filterset_class = ExamFilter

    def get_table_data(self):
        archive_pk = self.kwargs.get('pk')
        if archive_pk:
            return ExamFile.objects.filter(archive=archive_pk)
        return ExamFile.objects.all()

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        archive_pk = self.kwargs.get('pk')
        context['collection'] = ExamArchive.objects.filter(pk=archive_pk).first()
        return context

    def dispatch(self, request, *args, **kwargs):
        protected_view = exam_bank_access_required(super().dispatch)
        return protected_view(request, *args, **kwargs)
