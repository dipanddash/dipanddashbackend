import multiprocessing
import os

# App Platform exposes the runtime port via PORT.
bind = f"0.0.0.0:{os.getenv('PORT', '8080')}"
backlog = 2048

# Reasonable worker default for small instances.
workers = max(2, multiprocessing.cpu_count() * 2 + 1)
worker_class = "sync"
worker_connections = 1000
timeout = 60
keepalive = 2

# Container logging should go to stdout/stderr.
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Ensure Gunicorn knows which app to load when started with only -c.
wsgi_app = "food.wsgi:application"
