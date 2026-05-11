import logging

from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect, render
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin

from .filters import ExamFilter
from .forms import ExamArchiveUploadForm, ExamUploadForm
from .models import ExamArchive, ExamFile
from .tables import ExamFileTable

logger = logging.getLogger('date')


def user_type(user):
    if not user.is_authenticated:
        return False
    return user.membership_type.permission_profile != 3


@user_passes_test(user_type, login_url='/members/login/')
def exams_index(request):
    archives = ExamArchive.objects.all().order_by('title')
    return render(request, 'archive/exams_index.html', {
        'type': "exams",
        'collections': archives,
    })


@user_passes_test(user_type, login_url='/members/login/')
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


@user_passes_test(user_type, login_url='/members/login/')
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


class FilteredExamsListView(UserPassesTestMixin, SingleTableMixin, FilterView):
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

    def test_func(self):
        return self.request.user.membership_type.permission_profile != 3
