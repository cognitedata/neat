from prometheus_client import Counter, make_asgi_app

counter = Counter("started_workflows", "Description of counter")
prometheus_app = make_asgi_app()
