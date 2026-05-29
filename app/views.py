import os
import uuid
import threading
from django.shortcuts import render
from django.http import FileResponse, Http404, StreamingHttpResponse
from django.conf import settings
import time

from .forms import VideoForm
from .utils import cut_video, make_zip

# In-memory progress store: { task_id: int (0-100) }
_progress_store = {}


def index(request):
    if request.method == "POST":
        form = VideoForm(request.POST, request.FILES)

        if form.is_valid():
            video_file = request.FILES["video"]
            clips_count = form.cleaned_data["clips_count"]
            duration = form.cleaned_data["clip_duration"]

            task_id = str(uuid.uuid4())
            base_dir = os.path.join(settings.MEDIA_ROOT, task_id)
            os.makedirs(base_dir, exist_ok=True)

            input_path = os.path.join(base_dir, "input.mp4")
            with open(input_path, "wb+") as f:
                for chunk in video_file.chunks():
                    f.write(chunk)

            clips_folder = os.path.join(base_dir, "clips")
            zip_path = os.path.join(base_dir, "output.zip")

            # Init progress
            _progress_store[task_id] = 0

            def update_progress(percent):
                _progress_store[task_id] = percent

            # 1. Cut video with real progress
            clips = cut_video(
                input_path, clips_folder, clips_count, duration,
                progress_callback=update_progress
            )

            if not clips:
                _progress_store.pop(task_id, None)
                raise Http404("No clips generated. FFmpeg failed.")

            # 2. Zip
            zip_file = make_zip(clips, zip_path)
            _progress_store[task_id] = 100  # done

            if not os.path.exists(zip_file):
                raise Http404("ZIP file not created.")

            # 3. Return file (include task_id as header so frontend can stop polling)
            response = FileResponse(
                open(zip_file, "rb"),
                as_attachment=True,
                filename="clips.zip"
            )
            response["X-Task-Id"] = task_id
            return response

    else:
        form = VideoForm()

    return render(request, "index.html", {"form": form})


def ffmpeg_progress(request):
    """
    Real SSE progress stream for a given task_id.
    URL: /progress/?task_id=<uuid>
    """
    task_id = request.GET.get("task_id")

    def event_stream():
        last = -1
        timeout = 300  # max 5 min
        elapsed = 0

        while elapsed < timeout:
            current = _progress_store.get(task_id, 0)

            if current != last:
                yield f"data: {current}\n\n"
                last = current

            if current >= 100:
                _progress_store.pop(task_id, None)
                break

            time.sleep(0.5)
            elapsed += 0.5

    return StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream"
    )