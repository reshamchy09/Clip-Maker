import os
import uuid
import threading
import time

from django.shortcuts import render
from django.http import FileResponse, Http404, StreamingHttpResponse
from django.conf import settings

from .forms import VideoForm
from .utils import cut_video, make_zip


_progress_store = {}
_result_store = {}   # store final zip path


def process_video(task_id, input_path, clips_folder, zip_path, clips_count, duration):
    try:
        def update_progress(p):
            _progress_store[task_id] = p

        clips = cut_video(
            input_path,
            clips_folder,
            clips_count,
            duration,
            progress_callback=update_progress
        )

        if not clips:
            _progress_store[task_id] = -1
            return

        zip_file = make_zip(clips, zip_path)

        _result_store[task_id] = zip_file
        _progress_store[task_id] = 100

    except Exception:
        _progress_store[task_id] = -1


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

            # save file safely (NO memory load)
            with open(input_path, "wb") as f:
                for chunk in video_file.chunks():
                    f.write(chunk)

            clips_folder = os.path.join(base_dir, "clips")
            zip_path = os.path.join(base_dir, "output.zip")

            _progress_store[task_id] = 0

            # RUN IN BACKGROUND THREAD (fix crash)
            thread = threading.Thread(
                target=process_video,
                args=(task_id, input_path, clips_folder, zip_path, clips_count, duration)
            )
            thread.start()

            return render(request, "index.html", {
                "form": VideoForm(),
                "task_id": task_id
            })

    return render(request, "index.html", {"form": VideoForm()})


def ffmpeg_progress(request):
    task_id = request.GET.get("task_id")

    def stream():
        last = -1
        timeout = 300
        elapsed = 0

        while elapsed < timeout:
            value = _progress_store.get(task_id, 0)

            if value != last:
                yield f"data: {value}\n\n"
                last = value

            if value == 100:
                break

            if value == -1:
                yield "data: error\n\n"
                break

            time.sleep(0.5)
            elapsed += 0.5

    return StreamingHttpResponse(stream(), content_type="text/event-stream")


def download_result(request, task_id):
    zip_file = _result_store.get(task_id)

    if not zip_file or not os.path.exists(zip_file):
        raise Http404("File not ready")

    return FileResponse(open(zip_file, "rb"), as_attachment=True, filename="clips.zip")