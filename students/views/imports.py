import logging

logger = logging.getLogger(__name__)

"""CSV bulk import upload and upload history."""

from django.contrib import messages
from django.shortcuts import render

from ..audit import log_action
from ..forms import (
    CSVUploadForm,
)
from ..models import (
    CSVUpload,
)
from ..pagination import paginate
from ..upload_router import process_any_csv_upload
from .common import admin_required


@admin_required
def csv_upload(request):
    result = None
    form = CSVUploadForm()

    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.save(commit=False)
            upload.uploaded_by = request.user.get_full_name() or request.user.username
            upload.save()

            try:
                result = process_any_csv_upload(upload)
            except Exception as exc:  # a bad sheet must not 500 the whole page
                logger.exception("CSV import failed for upload %s", upload.pk)
                upload.is_processed = False
                upload.errors = f"Import failed: {exc}"[:2000]
                upload.save(update_fields=["is_processed", "errors"])
                messages.error(
                    request,
                    "Import fail ho gaya. File format check karein; poora error upload history mein hai.",
                )
                return render(request, 'admin_dashboard/upload_csv.html',
                              {'form': form, 'result': {'created': 0, 'updated': 0, 'errors': [str(exc)[:200]]}})
            # Save generic counters for any dataset type
            upload.is_processed = True
            upload.records_created = int(result.get("created", 0) or 0)
            upload.records_updated = int(result.get("updated", 0) or 0)
            upload.errors = "\n".join(result.get("errors", []) or [])
            upload.save()
            log_action(request, "csv.import", upload,
                       detail=f"created={upload.records_created} updated={upload.records_updated} errors={len(result.get('errors', []) or [])}")

            messages.success(
                request,
                f"✅ CSV processed: {result['created']} created, {result['updated']} updated, "
                f"{len(result['errors'])} errors."
            )
        else:
            messages.error(request, "❌ Form validation failed. Please check the file.")

    return render(request, 'admin_dashboard/upload_csv.html', {
        'form': form,
        'result': result,
    })


@admin_required
def upload_history(request):
    uploads = paginate(request, CSVUpload.objects.all())
    return render(request, 'admin_dashboard/upload_history.html', {'uploads': uploads})

