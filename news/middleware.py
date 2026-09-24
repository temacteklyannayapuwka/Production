"""HTTP-level indexing safeguards for non-public and error responses."""

from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class SearchEnginePolicyMiddleware:
    """Add X-Robots-Tag where an HTML meta tag cannot be relied upon."""

    protected_prefixes = ("/admin/", "/ckeditor/", "/search/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().partition(":")[0].lower()
        canonical_host = urlsplit(settings.PUBLIC_SITE_URL).hostname
        if canonical_host and host == f"www.{canonical_host}":
            return HttpResponsePermanentRedirect(
                f"{settings.PUBLIC_SITE_URL}{request.get_full_path()}"
            )

        response = self.get_response(request)

        if host in settings.SEO_NOINDEX_HOSTS:
            response["X-Robots-Tag"] = "noindex, nofollow"
        elif request.path.startswith(self.protected_prefixes):
            response["X-Robots-Tag"] = "noindex, nofollow"
        elif response.status_code >= 400:
            response["X-Robots-Tag"] = "noindex, follow"
        return response
