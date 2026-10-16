import multiprocessing

wsgi_app = "radiotsekh.wsgi:application"
bind = "127.0.0.1:8000"  # снаружи — только через nginx
workers = min(multiprocessing.cpu_count() * 2 + 1, 5)
timeout = 60
accesslog = "-"
errorlog = "-"
