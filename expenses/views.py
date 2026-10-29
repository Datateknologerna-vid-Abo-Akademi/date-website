import logging
from mimetypes import guess_type

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from .forms import ExpenseClaimForm
from .models import ExpenseClaim, ExpenseReceipt
from .tasks import generate_expense_pdf

logger = logging.getLogger("date")

CLAIMS_PER_PAGE = 50


def _claim_queryset():
    return ExpenseClaim.objects.select_related("submitted_by", "reviewed_by")


def _get_visible_claim(user, pk):
    """Return the claim, or 404 for a member who does not own it.

    Staff read every claim; a signed-in member reads only their own. The 404
    rather than a 403 is deliberate: it does not confirm that somebody else's
    claim exists.
    """
    claim = get_object_or_404(_claim_queryset(), pk=pk)
    if claim.submitted_by_id != user.pk and not user.is_staff:
        raise Http404
    return claim


def _enqueue_pdf_generation(claim_id):
    """Queue the PDF task without letting a broker outage fail the submission."""
    try:
        generate_expense_pdf.delay(claim_id)
    except Exception:
        # The claim and its receipts are already committed. Losing the queue
        # message costs the automatic PDF, which the admin action can rebuild;
        # it must not show the member an error page for a saved claim.
        logger.exception("Could not queue PDF generation for expense claim %s", claim_id)


@login_required
def expense_list(request):
    claims = _claim_queryset()
    if not request.user.is_staff:
        claims = claims.filter(submitted_by=request.user)
    page = Paginator(claims, CLAIMS_PER_PAGE).get_page(request.GET.get("page"))
    return render(request, "expenses/list.html", {"claims": page, "is_staff": request.user.is_staff})


@login_required
def expense_create(request):
    if request.method == "POST":
        form = ExpenseClaimForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                claim = form.save(commit=False)
                claim.submitted_by = request.user
                claim.save()
                for uploaded in form.cleaned_data["receipts"]:
                    ExpenseReceipt.objects.create(claim=claim, file=uploaded)
                # The worker would otherwise race the transaction and read a
                # claim whose receipts are not committed yet.
                transaction.on_commit(lambda: _enqueue_pdf_generation(claim.pk))
            messages.success(request, _("Kostnadsersättningen har skickats in."))
            return redirect("expenses:detail", pk=claim.pk)
    else:
        # Member.get_full_name() returns a lone space when neither name is set.
        default_recipient = request.user.get_full_name().strip() or request.user.username
        form = ExpenseClaimForm(initial={"recipient_name": default_recipient})
    return render(request, "expenses/create.html", {"form": form})


@login_required
def expense_detail(request, pk):
    claim = _get_visible_claim(request.user, pk)
    return render(request, "expenses/detail.html", {"claim": claim, "is_staff": request.user.is_staff})


@login_required
def receipt_file(request, pk):
    receipt = get_object_or_404(ExpenseReceipt.objects.select_related("claim"), pk=pk)
    claim = receipt.claim
    if claim.submitted_by_id != request.user.pk and not request.user.is_staff:
        raise Http404
    content_type = guess_type(receipt.file.name)[0] or "application/octet-stream"
    try:
        response = FileResponse(receipt.file.open("rb"), content_type=content_type)
    except FileNotFoundError:
        logger.warning("Receipt file missing in storage: %s", receipt.file.name)
        raise Http404(_("Kvittot finns inte.")) from None
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
def download_pdf(request, pk):
    if not request.user.is_staff:
        raise Http404
    claim = _get_visible_claim(request.user, pk)
    if not claim.pdf:
        raise Http404(_("PDF:en har inte genererats än."))
    try:
        response = FileResponse(
            claim.pdf.open("rb"),
            content_type="application/pdf",
            as_attachment=True,
            filename=claim.pdf_filename,
        )
    except FileNotFoundError:
        logger.warning("Claim PDF missing in storage: %s", claim.pdf.name)
        raise Http404(_("PDF:en har inte genererats än.")) from None
    response["Cache-Control"] = "private, no-store"
    return response
