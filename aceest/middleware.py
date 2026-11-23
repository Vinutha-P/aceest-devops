"""WSGI middleware.

PrefixMiddleware lets one Kubernetes ingress expose several deployments under
path prefixes (``/rolling``, ``/canary``, ...) without rewriting URLs: a request
for ``/canary/version`` is served as ``/version`` with ``SCRIPT_NAME=/canary``.
Requests without the prefix (e.g. kubelet probes on ``/health``) pass through.
"""


class PrefixMiddleware:
    def __init__(self, wsgi_app, prefix):
        self.wsgi_app = wsgi_app
        self.prefix = "/" + prefix.strip("/") if prefix and prefix.strip("/") else ""

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        if self.prefix and (path == self.prefix or path.startswith(self.prefix + "/")):
            environ["SCRIPT_NAME"] = environ.get("SCRIPT_NAME", "") + self.prefix
            environ["PATH_INFO"] = path[len(self.prefix):] or "/"
        return self.wsgi_app(environ, start_response)
