from django.db import models
from django.contrib.auth.models import User


# =========================================================
# CONVERSATION
# =========================================================

class Conversation(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="conversations"
    )

    title = models.CharField(
        max_length=200,
        default="New conversation"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title


# =========================================================
# MESSAGE
# =========================================================

class Message(models.Model):

    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages"
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES
    )

    content = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"


# =========================================================
# UPLOADED FILE
# =========================================================

class UploadedFile(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="uploaded_files"
    )

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="uploaded_files",
        null=True,
        blank=True
    )

    file = models.FileField(
        upload_to="uploads/%Y/%m/%d/"
    )

    original_name = models.CharField(
        max_length=255
    )

    file_type = models.CharField(
        max_length=100,
        blank=True
    )

    file_size = models.PositiveBigIntegerField(
        default=0
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.original_name