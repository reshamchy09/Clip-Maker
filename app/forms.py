from django import forms


class VideoForm(forms.Form):
    video = forms.FileField()

    clips_count = forms.IntegerField(min_value=1, max_value=50)
    clip_duration = forms.IntegerField(min_value=5, max_value=600)