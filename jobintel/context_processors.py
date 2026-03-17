from accounts.models import GmailToken

def gmail_status(request):
    if request.user.is_authenticated:
        return {
            "gmail_connected": GmailToken.objects.filter(
                user=request.user
            ).exists()
        }

    return {"gmail_connected": False}
