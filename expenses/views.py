from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ExpenseClaimForm
from .models import ExpenseClaim, ExpenseReceipt
from .tasks import generate_expense_pdf


@login_required
def expense_list(request):
    if request.user.is_staff:
        claims = ExpenseClaim.objects.select_related('submitted_by').all()
    else:
        claims = ExpenseClaim.objects.filter(submitted_by=request.user)
    return render(request, 'expenses/list.html', {'claims': claims})


@login_required
def expense_create(request):
    if request.method == 'POST':
        form = ExpenseClaimForm(request.POST, request.FILES)
        if form.is_valid():
            claim = form.save(commit=False)
            claim.submitted_by = request.user
            claim.save()
            for f in form.cleaned_data['receipts']:
                ExpenseReceipt.objects.create(claim=claim, file=f)
            generate_expense_pdf.delay(claim.pk)
            return redirect('expenses:detail', pk=claim.pk)
    else:
        form = ExpenseClaimForm()
    return render(request, 'expenses/create.html', {'form': form})


@login_required
def expense_detail(request, pk):
    claim = get_object_or_404(ExpenseClaim, pk=pk)
    if claim.submitted_by != request.user and not request.user.is_staff:
        raise Http404
    return render(request, 'expenses/detail.html', {'claim': claim})


@user_passes_test(lambda u: u.is_staff)
def download_pdf(request, pk):
    claim = get_object_or_404(ExpenseClaim, pk=pk)
    if not claim.pdf:
        return HttpResponse('PDF not yet generated.', status=404)
    try:
        if getattr(settings, 'USE_S3', False):
            return redirect(claim.pdf.url)
        filename = claim.pdf.name.split('/')[-1]
        pdf_bytes = claim.pdf.read()
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception:
        return HttpResponse('Could not retrieve PDF.', status=500)
