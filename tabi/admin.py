from django.contrib import admin
from .models import (User, Post, Follow, Profile, Interest, AnonymousProfile, Comment, Hashtag,
                     FriendRequest, Friendship, Community, CommunityMembership, Notification,
                     Conversation, Message, Report, Streak, BlockedUser)

@admin.action(description="Suspend selected users")
def suspend_users(modeladmin, request, queryset): queryset.update(status="suspended")
@admin.action(description="Block selected users")
def block_users(modeladmin, request, queryset): queryset.update(status="blocked")
@admin.action(description="Restore selected users")
def restore_users(modeladmin, request, queryset): queryset.update(status="active")
@admin.action(description="Dismiss selected reports")
def dismiss_reports(modeladmin, request, queryset): queryset.update(status="dismissed", reviewer=request.user)
@admin.action(description="Remove reported posts")
def remove_reported_posts(modeladmin, request, queryset):
    for report in queryset:
        if report.post_id: report.post.delete()
        report.status = "actioned"; report.reviewer = request.user; report.save()

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "status", "is_staff")
    list_filter = ("status", "is_staff")
    search_fields = ("username", "email")
    actions = (suspend_users, block_users, restore_users)

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "reporter", "reason", "status", "auto_flagged", "created_at")
    list_filter = ("status", "auto_flagged")
    actions = (dismiss_reports, remove_reported_posts)

@admin.register(AnonymousProfile)
class AnonymousProfileAdmin(admin.ModelAdmin):
    """Restricted admin-only view of anonymous identity links."""
    list_display = ("display_name", "user")
    search_fields = ("display_name", "user__username")

for model in (Post, Follow, Profile, Interest, Comment, Hashtag, FriendRequest, Friendship,
              Community, CommunityMembership, Notification, Conversation, Message, Streak, BlockedUser):
    admin.site.register(model)
