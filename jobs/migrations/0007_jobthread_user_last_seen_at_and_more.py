from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0006_jobthread_followup_dismissed"),
    ]

    operations = [
        migrations.AddField(
            model_name="jobthread",
            name="user_last_seen_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="jobthread",
            index=models.Index(fields=["-last_activity_at"], name="jobs_jobthr_last_ac_desc_idx"),
        ),
    ]
