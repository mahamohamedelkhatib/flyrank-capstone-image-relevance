import time

from app import repository
from app.vectors import embed_images
from app.worker import pending_left, process_one


def run_job(job_id: int) -> None:
    """Tag every pending image, embed the new ones, and keep the job row up to date."""
    error = None
    try:
        while True:
            result = process_one()
            if result is not None:
                repository.refresh_job_progress(job_id)
                continue
            if pending_left() == 0:
                break
            time.sleep(2)  # some images are waiting for their retry time
        embed_images()
    except Exception as e:
        error = f"{type(e).__name__}: {e}"[:500]
    repository.refresh_job_progress(job_id)
    repository.finish_job(job_id, error)
