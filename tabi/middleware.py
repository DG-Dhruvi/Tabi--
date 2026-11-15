from django.http import HttpResponseForbidden

class AccountStatusMiddleware:
    """Keep already-authenticated suspended/blocked accounts from changing state."""
    def __init__(self, get_response): self.get_response = get_response
    def __call__(self, request):
        if request.user.is_authenticated and request.user.status != "active":
            if request.method == "POST" and not request.path.startswith("/admin/"):
                return HttpResponseForbidden("This account cannot post or change content.")
        return self.get_response(request)
