from .models import Conversation

def sidebar_context(request):
    """Small account counters shared by the Tabi navigation."""
    if not request.user.is_authenticated:
        return {"unread_notifications": 0, "inbox_unread": 0}
    unread_notifications = request.user.notifications.filter(read=False).count()
    inbox_unread = Conversation.objects.filter(
        participants=request.user,
        messages__read=False,
    ).exclude(messages__sender=request.user).distinct().count()
    return {"unread_notifications": unread_notifications, "inbox_unread": inbox_unread}
