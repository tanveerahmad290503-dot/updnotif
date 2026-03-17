from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from .processor import process_unprocessed_emails


@login_required
def process_emails_view(request):
    process_unprocessed_emails(request.user)
    return HttpResponse("Emails processed!")
