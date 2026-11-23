"""Gunicorn settings for the container image (v3.0.1)."""
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"
workers = int(os.environ.get("GUNICORN_WORKERS", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "2"))

# Create the app (and run DB migrations) once in the master before forking workers
preload_app = True

# Kubernetes sends SIGTERM on rollout; finish in-flight requests before exiting
graceful_timeout = 20
timeout = 30

# Writable tmp dir even with a read-only root filesystem
worker_tmp_dir = "/dev/shm"

# Access log to stdout, including which version/track served the request
accesslog = "-"
errorlog = "-"
access_log_format = (
    '%(h)s "%(r)s" %(s)s %(b)s %(M)sms '
    'version=%({x-app-version}o)s track=%({x-deployment-track}o)s'
)
