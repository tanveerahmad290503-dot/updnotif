import uuid
from django.db import models
from django.contrib.auth.models import User


class GmailToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    access_token = models.TextField()
    refresh_token = models.TextField()

    token_uri = models.TextField(default="https://oauth2.googleapis.com/token")
    client_id = models.TextField()
    client_secret = models.TextField()

    scopes = models.JSONField()

    expires_at = models.DateTimeField()

        # ✅ NEW — Gmail connection status
    is_active = models.BooleanField(
        default=True
    )
    gmail_history_id = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )
    # ✅ NEW — store OAuth error reason
    last_error = models.TextField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"GmailToken for {self.user.email}"
