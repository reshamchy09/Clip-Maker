from django.db import models


class VideoUpload(models.Model):
    video = models.FileField(upload_to="uploads/")
    clips_count = models.IntegerField(default=5)
    clip_duration = models.IntegerField(default=15)
    aspect_ratio = models.CharField(
        max_length=10,
        choices=[("9:16", "9:16"), ("1:1", "1:1"), ("16:9", "16:9")],
        default="9:16"
    )
    created_at = models.DateTimeField(auto_now_add=True)


class Clip(models.Model):
    video = models.ForeignKey(VideoUpload, on_delete=models.CASCADE)
    file = models.FileField(upload_to="clips/")
    index = models.IntegerField()


class ProcessedVideo(models.Model):
    clip = models.ForeignKey(Clip, on_delete=models.CASCADE)
    file = models.FileField(upload_to="processed/")
    created_at = models.DateTimeField(auto_now_add=True)


class Subtitle(models.Model):
    clip = models.ForeignKey(Clip, on_delete=models.CASCADE)
    text = models.TextField()


class Hashtag(models.Model):
    clip = models.ForeignKey(Clip, on_delete=models.CASCADE)
    tags = models.TextField()


class ExportHistory(models.Model):
    zip_file = models.FileField(upload_to="exports/")
    created_at = models.DateTimeField(auto_now_add=True)