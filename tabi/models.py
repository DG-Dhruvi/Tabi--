from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import FileExtensionValidator
import os


class User(AbstractUser):
    STATUS_CHOICES = [("active", "Active"), ("suspended", "Suspended"), ("blocked", "Blocked")]
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="active")

class Interest(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(unique=True)
    def __str__(self): return self.name

def profile_upload_path(instance, filename):
    return "profiles/%s/%s" % (instance.user_id, os.path.basename(filename))

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    bio = models.TextField(max_length=500, blank=True)
    picture = models.ImageField(upload_to=profile_upload_path, blank=True, validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])])
    location = models.CharField(max_length=100, blank=True)
    interests = models.ManyToManyField(Interest, blank=True, related_name="profiles")
    def __str__(self): return "Profile of %s" % self.user.username

class AnonymousProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="anonymous_profile")
    display_name = models.CharField(max_length=50)
    avatar = models.CharField(max_length=20, default="🌱")
    def __str__(self): return "%s (private link)" % self.display_name

class Post(models.Model):
    content = models.CharField(max_length=500)
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name="author")
    date = models.DateTimeField(auto_now_add=True)
    likes = models.ManyToManyField(User, related_name="liked_postes",blank=True)
    image = models.ImageField(upload_to="posts/", blank=True, validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])])
    hashtags = models.ManyToManyField("Hashtag", blank=True, related_name="posts")
    community = models.ForeignKey("Community", null=True, blank=True, on_delete=models.SET_NULL, related_name="posts")
    is_anonymous = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Post {self.id} made by {self.user} on {self.date.strftime('%d %b %Y %H:%M:%S')}"
    
class Follow(models.Model):
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name="who_is_following")
    user_follower = models.ForeignKey(User,on_delete=models.CASCADE,related_name="who_is_being_followed")
    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "user_follower"], name="unique_follow_pair"), models.CheckConstraint(condition=~models.Q(user=models.F("user_follower")), name="no_self_follow")]
    
    def __str__(self):
        return f"{self.user} is following {self.user_follower}"          

class Hashtag(models.Model):
    name = models.CharField(max_length=60, unique=True)
    def __str__(self): return "#" + self.name

class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comments")
    content = models.CharField(max_length=500)
    date = models.DateTimeField(auto_now_add=True)
    is_anonymous = models.BooleanField(default=False)

class FriendRequest(models.Model):
    STATUS = [("pending", "Pending"), ("accepted", "Accepted"), ("rejected", "Rejected")]
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_friend_requests")
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_friend_requests")
    status = models.CharField(max_length=10, choices=STATUS, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: constraints = [models.UniqueConstraint(fields=["sender", "recipient"], name="unique_friend_request")]

class Friendship(models.Model):
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="friendships")
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name="friendships_as_other")
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: constraints = [models.UniqueConstraint(fields=["user1", "user2"], name="unique_friendship")]

class BlockedUser(models.Model):
    blocker = models.ForeignKey(User, on_delete=models.CASCADE, related_name="blocked_users")
    blocked = models.ForeignKey(User, on_delete=models.CASCADE, related_name="blocked_by_users")
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: constraints = [models.UniqueConstraint(fields=["blocker", "blocked"], name="unique_blocked_user"), models.CheckConstraint(condition=~models.Q(blocker=models.F("blocked")), name="no_self_block")]

class Community(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(max_length=500)
    interests = models.ManyToManyField(Interest, blank=True, related_name="communities")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="created_communities")
    created_at = models.DateTimeField(auto_now_add=True)

class CommunityMembership(models.Model):
    ROLES = [("member", "Member"), ("moderator", "Moderator"), ("owner", "Owner")]
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="community_memberships")
    role = models.CharField(max_length=10, choices=ROLES, default="member")
    class Meta: constraints = [models.UniqueConstraint(fields=["community", "user"], name="unique_community_membership")]

class Notification(models.Model):
    kind = models.CharField(max_length=30)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications_sent")
    post = models.ForeignKey(Post, null=True, blank=True, on_delete=models.CASCADE)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class Conversation(models.Model):
    participants = models.ManyToManyField(User, related_name="conversations")
    updated_at = models.DateTimeField(auto_now=True)

class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="messages_sent")
    content = models.CharField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

class Report(models.Model):
    STATUS = [("pending", "Pending"), ("reviewed", "Reviewed"), ("actioned", "Actioned"), ("dismissed", "Dismissed")]
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reports")
    post = models.ForeignKey(Post, null=True, blank=True, on_delete=models.SET_NULL)
    comment = models.ForeignKey(Comment, null=True, blank=True, on_delete=models.SET_NULL)
    reported_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="reports_against")
    reason = models.CharField(max_length=300)
    status = models.CharField(max_length=12, choices=STATUS, default="pending")
    reviewer = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_reports")
    auto_flagged = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class Streak(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="streaks")
    interest = models.ForeignKey(Interest, on_delete=models.CASCADE, related_name="streaks")
    current = models.PositiveIntegerField(default=0)
    longest = models.PositiveIntegerField(default=0)
    last_activity = models.DateField(null=True, blank=True)
    class Meta: constraints = [models.UniqueConstraint(fields=["user", "interest"], name="unique_user_interest_streak")]
