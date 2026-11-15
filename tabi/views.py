import json
import re
import csv
from datetime import timedelta
from django.contrib import messages as flash_messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, models
from django.http import HttpResponseRedirect, JsonResponse, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST, require_GET, require_http_methods
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.utils import timezone
from django.utils.text import slugify
from .models import (User, Post, Follow, Profile, AnonymousProfile, Interest, Hashtag,
                     Comment, FriendRequest, Friendship, Community, CommunityMembership,
                     Conversation, Message, Notification, Report, Streak, BlockedUser)
from .forms import ProfileForm, PostForm, CommentForm, CommunityForm

def visible_name(post):
    return "Anonymous member" if post.is_anonymous else post.user.username

def _page(request, qs):
    return Paginator(qs, 10).get_page(request.GET.get("page"))

def index(request):
    posts = Post.objects.select_related("user", "community").prefetch_related("likes", "hashtags", "comments").order_by("-date")
    profile = Profile.objects.filter(user=request.user).first() if request.user.is_authenticated else None
    interests = profile.interests.all()[:5] if profile else []
    if profile and profile.interests.exists():
        suggestions = User.objects.filter(profile__interests__in=profile.interests.all(), status="active").exclude(pk=request.user.pk).distinct()[:6]
    elif request.user.is_authenticated:
        suggestions = User.objects.filter(status="active").exclude(pk=request.user.pk).order_by("username")[:6]
    else:
        suggestions = User.objects.filter(status="active").order_by("username")[:6]
    joined_spaces = CommunityMembership.objects.filter(user=request.user).select_related("community")[:4] if request.user.is_authenticated else []
    streak = Streak.objects.filter(user=request.user).order_by("-current").first() if request.user.is_authenticated else None
    featured_space = Community.objects.order_by("created_at").first()
    featured_image = Post.objects.filter(community=featured_space, image__gt="").order_by("-date").first() if featured_space else None
    context = {"posts_of_the_page": _page(request, posts), "post_form": PostForm(), "profile": profile,
               "curiosities": interests, "suggestions": suggestions, "joined_spaces": joined_spaces,
               "streak": streak, "featured_space": featured_space, "featured_image": featured_image}
    return render(request, "tabi/index.html", context)

@login_required
def following(request):
    ids = Follow.objects.filter(user=request.user).values_list("user_follower_id", flat=True)
    posts = Post.objects.filter(user_id__in=ids).order_by("-date")
    profile = Profile.objects.filter(user=request.user).first()
    return render(request, "tabi/following.html", {"posts_of_the_page": _page(request, posts), "profile": profile, "curiosities": profile.interests.all()[:5] if profile else [], "streak": Streak.objects.filter(user=request.user).order_by("-current").first()})

@login_required
@require_POST
def newPost(request):
    form = PostForm(request.POST, request.FILES)
    if not form.is_valid():
        flash_messages.error(request, "Please correct the post form and try again.")
        return redirect("index")
    post = form.save(commit=False); post.user = request.user
    post.is_anonymous = request.POST.get("author_mode") == "anonymous" or request.POST.get("is_anonymous") == "on"
    community_id = request.POST.get("community")
    if community_id:
        post.community = get_object_or_404(Community, pk=community_id)
    if post.is_anonymous:
        AnonymousProfile.objects.get_or_create(user=request.user, defaults={"display_name": "Quiet traveler"})
    post.save()
    content_tags = re.findall(r"#([\w-]{1,60})", post.content, flags=re.UNICODE)
    form_tags = re.findall(r"#?([\w-]{1,60})", request.POST.get("hashtags", "")[:200], flags=re.UNICODE)
    for tag in set(content_tags + form_tags):
        tag_obj, _ = Hashtag.objects.get_or_create(name=tag.lower())
        post.hashtags.add(tag_obj)
    if post.community_id and not CommunityMembership.objects.filter(community=post.community, user=request.user).exists():
        post.delete(); return HttpResponseForbidden("Join this community before posting.")
    if post.community_id:
        for member_id in CommunityMembership.objects.filter(community=post.community).exclude(user=request.user).values_list("user_id", flat=True):
            Notification.objects.create(kind="community post", recipient_id=member_id, actor=request.user, post=post)
    for tag in post.hashtags.all():
        interest = Interest.objects.filter(slug=slugify(tag.name)).first()
        if interest:
            streak, _ = Streak.objects.get_or_create(user=request.user, interest=interest)
            today = timezone.localdate()
            if streak.last_activity != today:
                streak.current = streak.current + 1 if streak.last_activity == today - timedelta(days=1) else 1
                streak.longest = max(streak.longest, streak.current); streak.last_activity = today; streak.save()
    return redirect("index")

@login_required
@require_POST
def editPost(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if post.user_id != request.user.id: return JsonResponse({"error": "You cannot edit this post."}, status=403)
    try: data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError): return JsonResponse({"error": "Invalid JSON."}, status=400)
    content = data.get("content", "").strip()
    if not content or len(content) > 500: return JsonResponse({"error": "Post text must be between 1 and 500 characters."}, status=400)
    post.content = content; post.edited_at = timezone.now(); post.save(update_fields=["content", "edited_at"])
    return JsonResponse({"content": post.content})

@login_required
@require_http_methods(["GET", "POST"])
def edit_post_page(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if post.user_id != request.user.id:
        return HttpResponseForbidden("You can only edit your own posts.")
    if request.method == "POST":
        content = request.POST.get("content", "").strip()
        if not content or len(content) > 500:
            return render(request, "tabi/edit.html", {"post": post, "error": "Post text must contain 1 to 500 characters."}, status=400)
        post.content = content; post.edited_at = timezone.now(); post.save(update_fields=["content", "edited_at"])
        flash_messages.success(request, "Your post has been updated.")
        return redirect("profile", user_id=request.user.id)
    return render(request, "tabi/edit.html", {"post": post})

def profile(request, user_id):
    member = get_object_or_404(User, pk=user_id)
    posts = Post.objects.filter(user=member).order_by("-date")
    profile_cover = posts.exclude(image="").first()
    follows = Follow.objects.filter(user=request.user, user_follower=member).exists() if request.user.is_authenticated else False
    profile_obj, _ = Profile.objects.get_or_create(user=member)
    suggestions = User.objects.filter(profile__interests__in=profile_obj.interests.all()).exclude(pk=member.pk).distinct()[:8]
    joined_spaces = CommunityMembership.objects.filter(user=member).select_related("community")[:4]
    streak = Streak.objects.filter(user=member).order_by("-current").first()
    is_friend = False; outgoing_request = False; incoming_request = False
    if request.user.is_authenticated and request.user != member:
        left, right = sorted((request.user.pk, member.pk))
        is_friend = Friendship.objects.filter(user1_id=left, user2_id=right).exists()
        outgoing_request = FriendRequest.objects.filter(sender=request.user, recipient=member, status="pending").exists()
        incoming_request = FriendRequest.objects.filter(sender=member, recipient=request.user, status="pending").exists()
    followers = Follow.objects.filter(user_follower=member).select_related("user")
    following = Follow.objects.filter(user=member).select_related("user_follower")
    friend_ids = []
    for friendship in Friendship.objects.filter(models.Q(user1=member) | models.Q(user2=member)):
        friend_ids.append(friendship.user2_id if friendship.user1_id == member.id else friendship.user1_id)
    friends_list = User.objects.filter(id__in=friend_ids)
    return render(request, "tabi/profile.html", {"posts_of_the_page": _page(request, posts), "username": member.username, "followers": followers, "following": following, "friends_list": friends_list, "is_following": follows, "user_profile": member, "profile": profile_obj, "profile_cover": profile_cover, "suggestions": suggestions, "is_friend": is_friend, "outgoing_request": outgoing_request, "incoming_request": incoming_request, "joined_spaces": joined_spaces, "streak": streak})

def login_view(request):
    if request.method == "POST":
        user = authenticate(request, username=request.POST.get("username", ""), password=request.POST.get("password", ""))
        if user is not None and user.status == "active":
            login(request, user); return redirect("index")
        return render(request, "tabi/login.html", {"message": "Invalid credentials or account unavailable."})
    return render(request, "tabi/login.html")

@require_POST
def logout_view(request):
    logout(request); return redirect("index")

def register(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip(); email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        if password != request.POST.get("confirmation"): return render(request, "tabi/register.html", {"message": "Passwords must match."})
        if len(username) < 3 or len(username) > 150: return render(request, "tabi/register.html", {"message": "Username must be 3–150 characters."})
        try:
            validate_email(email)
            validate_password(password, User(username=username, email=email))
        except ValidationError as error:
            return render(request, "tabi/register.html", {"message": " ".join(error.messages)})
        try:
            user = User.objects.create_user(username=username, email=email, password=password)
            Profile.objects.create(user=user); login(request, user); return redirect("index")
        except IntegrityError: return render(request, "tabi/register.html", {"message": "Username already taken."})
    return render(request, "tabi/register.html")

@login_required
@require_POST
def follow(request):
    member = get_object_or_404(User, username=request.POST.get("userfollow", ""))
    if member != request.user and not BlockedUser.objects.filter(models.Q(blocker=member, blocked=request.user) | models.Q(blocker=request.user, blocked=member)).exists():
        Follow.objects.get_or_create(user=request.user, user_follower=member)
        Notification.objects.get_or_create(kind="follow", recipient=member, actor=request.user)
    return redirect("profile", user_id=member.id)

@login_required
@require_POST
def unfollow(request):
    member = get_object_or_404(User, username=request.POST.get("userunfollow", ""))
    Follow.objects.filter(user=request.user, user_follower=member).delete(); return redirect("profile", user_id=member.id)

@login_required
@require_POST
def like(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    if post.likes.filter(pk=request.user.pk).exists(): post.likes.remove(request.user); liked = False
    else:
        post.likes.add(request.user); liked = True
        if post.user != request.user: Notification.objects.create(kind="like", recipient=post.user, actor=request.user, post=post)
    return JsonResponse({"liked": liked, "likes": post.likes.count()})

@login_required
def edit_profile(request):
    profile_obj, _ = Profile.objects.get_or_create(user=request.user)
    # Keep a useful starter list available even in a fresh installation.
    for name in ("Photography", "Art & design", "Nature", "Reading", "Music", "Cooking", "Gaming", "Travel", "Gardening", "Technology", "Fitness", "Writing"):
        Interest.objects.get_or_create(slug=slugify(name), defaults={"name": name})
    form = ProfileForm(request.POST or None, request.FILES or None, instance=profile_obj)
    if request.method == "POST" and form.is_valid():
        profile_obj = form.save()
        custom_interests = form.cleaned_data["custom_interests"]
        for name in custom_interests.split(","):
            name = name.strip()
            if not name:
                continue
            interest, _ = Interest.objects.get_or_create(slug=slugify(name), defaults={"name": name})
            profile_obj.interests.add(interest)
        flash_messages.success(request, "Your profile is updated.")
        return redirect("profile", user_id=request.user.id)
    return render(request, "tabi/profile_edit.html", {"form": form})

@login_required
@require_POST
def create_anonymous_profile(request):
    display_name = request.POST.get("display_name", "").strip()
    avatar = request.POST.get("avatar", "🌱")
    allowed_avatars = {"🌱", "🍃", "🌿", "🌼", "🍀"}
    if not display_name or len(display_name) > 50:
        flash_messages.error(request, "Choose an anonymous name between 1 and 50 characters.")
        return redirect("profile", user_id=request.user.id)
    AnonymousProfile.objects.update_or_create(user=request.user, defaults={"display_name": display_name, "avatar": avatar if avatar in allowed_avatars else "🌱"})
    flash_messages.success(request, "Your anonymous profile is ready. Your identity remains visible to moderators.")
    return redirect("profile", user_id=request.user.id)

def privacy(request): return render(request, "tabi/privacy.html")

def hashtag(request, tag):
    tag_obj = get_object_or_404(Hashtag, name=tag.lower())
    return render(request, "tabi/hashtag.html", {"tag": tag_obj, "posts_of_the_page": _page(request, tag_obj.posts.order_by("-date"))})

@login_required
@require_POST
def comment(request, post_id):
    post = get_object_or_404(Post, pk=post_id); form = CommentForm(request.POST)
    if not form.is_valid(): return JsonResponse({"error": "Comment must contain 1–500 characters."}, status=400)
    item = form.save(commit=False); item.post = post; item.user = request.user; item.is_anonymous = request.POST.get("is_anonymous") == "on"; item.save()
    if post.user != request.user: Notification.objects.create(kind="comment", recipient=post.user, actor=request.user, post=post)
    return JsonResponse({"id": item.id, "content": item.content, "author": "Anonymous member" if item.is_anonymous else request.user.username})

@require_GET
def search(request):
    term = request.GET.get("q", "").strip()[:80]
    results = {
        "users": list(User.objects.filter(username__icontains=term, status="active").values("username", "id")[:8]) if term else [],
        "posts": [{"id": p.id, "content": p.content[:160], "author": visible_name(p)} for p in Post.objects.filter(content__icontains=term).select_related("user")[:8]] if term else [],
        "hashtags": list(Hashtag.objects.filter(name__icontains=term).values("name")[:8]) if term else [],
        "communities": list(Community.objects.filter(name__icontains=term).values("name", "slug")[:8]) if term else [],
    }
    if "application/json" not in request.headers.get("accept", ""):
        return render(request, "tabi/search.html", {"term": term, "results": results})
    return JsonResponse(results)

def _community_cards(communities_qs):
    cards = []
    for community in communities_qs:
        photo = community.posts.exclude(image="").order_by("-date").first()
        cards.append({"community": community, "photo": photo})
    return cards

@login_required
@require_GET
def discover(request):
    cards = _community_cards(Community.objects.prefetch_related("interests", "memberships").order_by("name"))
    profile = Profile.objects.filter(user=request.user).first()
    suggestions = User.objects.filter(profile__interests__in=profile.interests.all(), status="active").exclude(pk=request.user.pk).distinct()[:4] if profile and profile.interests.exists() else User.objects.filter(status="active").exclude(pk=request.user.pk).order_by("username")[:4]
    return render(request, "tabi/discover.html", {"community_cards": cards, "featured": cards[0] if cards else None, "interests": Interest.objects.order_by("name")[:10], "suggestions": suggestions})

@login_required
def communities(request):
    form = CommunityForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            community = form.save(commit=False); community.created_by = request.user
            if Community.objects.filter(slug=community.slug).exists(): form.add_error("slug", "That community URL is already used.")
            else:
                community.save(); form.save_m2m(); CommunityMembership.objects.create(community=community, user=request.user, role="owner"); return redirect("community", slug=community.slug)
    memberships = CommunityMembership.objects.filter(user=request.user).select_related("community").prefetch_related("community__interests")
    joined_ids = memberships.values_list("community_id", flat=True)
    hosted = Community.objects.filter(created_by=request.user).prefetch_related("interests").order_by("name")
    joined = memberships.exclude(role="owner").order_by("community__name")
    available = Community.objects.exclude(pk__in=joined_ids).exclude(created_by=request.user).prefetch_related("interests").order_by("name")
    return render(request, "tabi/communities.html", {"joined_spaces": joined, "hosted_spaces": hosted, "available_cards": _community_cards(available), "form": form})

@login_required
def community_detail(request, slug):
    community = get_object_or_404(Community, slug=slug)
    if request.method == "POST":
        if request.POST.get("action") == "leave": CommunityMembership.objects.filter(community=community, user=request.user).exclude(role="owner").delete()
        else: CommunityMembership.objects.get_or_create(community=community, user=request.user)
        return redirect("community", slug=slug)
    posts = community.posts.select_related("user").order_by("-date")
    cover_post = posts.exclude(image="").first()
    membership = CommunityMembership.objects.filter(community=community, user=request.user).first()
    photo_posts = posts.exclude(image="").order_by("-date")
    community_members = CommunityMembership.objects.filter(community=community).select_related("user").order_by("role", "user__username")
    return render(request, "tabi/community.html", {"community": community, "cover_post": cover_post, "posts_of_the_page": _page(request, posts), "photo_posts": photo_posts, "community_members": community_members, "is_member": membership is not None, "can_moderate": membership is not None and membership.role in ("owner", "moderator")})

@login_required
def conversation_list(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        if not username:
            flash_messages.error(request, "Enter a username to start a conversation.")
            return redirect("messages")
        member = User.objects.filter(username__iexact=username, status="active").first()
        if member is None:
            flash_messages.error(request, "We couldn't find an active member with that username.")
            return redirect("messages")
        if member == request.user:
            flash_messages.error(request, "Choose another member to start a conversation.")
            return redirect("messages")
        if BlockedUser.objects.filter(models.Q(blocker=member, blocked=request.user) | models.Q(blocker=request.user, blocked=member)).exists(): return HttpResponseForbidden("This conversation cannot be started.")
        conversation = next((
            thread for thread in request.user.conversations.all()
            if thread.participants.count() == 2 and thread.participants.filter(pk=member.pk).exists()
        ), None)
        if conversation is None:
            conversation = Conversation.objects.create(); conversation.participants.add(request.user, member)
        return redirect("conversation", conversation_id=conversation.id)
    threads = request.user.conversations.prefetch_related("participants", "messages").order_by("-updated_at")
    active = threads.first()
    thread_messages = []
    if active:
        active.messages.exclude(sender=request.user).update(read=True)
        thread_messages = active.messages.select_related("sender").order_by("created_at")
    return render(request, "tabi/messages.html", {"conversations": threads, "conversation": active, "thread_messages": thread_messages})

@login_required
def conversation(request, conversation_id):
    thread = get_object_or_404(Conversation, pk=conversation_id, participants=request.user)
    if request.method == "POST":
        content = request.POST.get("content", "").strip()
        if content and len(content) <= 2000:
            Message.objects.create(conversation=thread, sender=request.user, content=content)
            return redirect("conversation", conversation_id=thread.id)
        flash_messages.error(request, "Messages must contain 1 to 2,000 characters.")
        return redirect("conversation", conversation_id=thread.id)
    thread.messages.exclude(sender=request.user).update(read=True)
    return render(request, "tabi/conversation.html", {"conversation": thread, "conversations": request.user.conversations.prefetch_related("participants", "messages").order_by("-updated_at"), "thread_messages": thread.messages.select_related("sender").order_by("created_at")})

@login_required
@require_GET
def poll_messages(request, conversation_id):
    thread = get_object_or_404(Conversation, pk=conversation_id, participants=request.user)
    try: after = int(request.GET.get("after", 0))
    except ValueError: return JsonResponse({"error": "Invalid message cursor."}, status=400)
    data = list(thread.messages.filter(id__gt=after).order_by("id").values("id", "content", "sender_id", "sender__username", "created_at"))
    return JsonResponse({"messages": data})

@login_required
def notifications(request):
    if request.method == "POST":
        request.user.notifications.filter(read=False).update(read=True)
        if request.headers.get("x-requested-with") == "XMLHttpRequest": return JsonResponse({"ok": True})
        flash_messages.success(request, "Notifications marked as read.")
        return redirect("notifications")
    items = request.user.notifications.order_by("-created_at")[:30]
    return render(request, "tabi/notifications.html", {"notifications": items, "unread": request.user.notifications.filter(read=False).count()})

@login_required
@require_GET
def unread_notifications(request):
    return JsonResponse({"unread": request.user.notifications.filter(read=False).count()})

@login_required
@require_POST
def send_friend_request(request, user_id):
    recipient = get_object_or_404(User, pk=user_id, status="active")
    if recipient == request.user: return JsonResponse({"error": "You cannot friend yourself."}, status=400)
    if BlockedUser.objects.filter(models.Q(blocker=recipient, blocked=request.user) | models.Q(blocker=request.user, blocked=recipient)).exists():
        return JsonResponse({"error": "This request cannot be sent."}, status=403)
    pair = sorted((request.user.pk, recipient.pk))
    if Friendship.objects.filter(user1_id=pair[0], user2_id=pair[1]).exists():
        if request.headers.get("x-requested-with") == "XMLHttpRequest": return JsonResponse({"ok": True, "status": "already friends"})
        flash_messages.info(request, "You are already friends.")
        return redirect("profile", user_id=recipient.pk)
    reciprocal = FriendRequest.objects.filter(sender=recipient, recipient=request.user, status="pending").first()
    if reciprocal:
        reciprocal.status = "accepted"
        reciprocal.save(update_fields=["status"])
        left, right = sorted((request.user.pk, recipient.pk))
        Friendship.objects.get_or_create(user1_id=left, user2_id=right)
        Notification.objects.create(kind="friend request accepted", recipient=recipient, actor=request.user)
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": True, "status": "friends"})
        flash_messages.success(request, "You are now friends.")
        return redirect("profile", user_id=recipient.pk)
    obj, created = FriendRequest.objects.get_or_create(sender=request.user, recipient=recipient, defaults={"status": "pending"})
    if not created and obj.status != "pending":
        obj.status = "pending"
        obj.save(update_fields=["status"])
        created = True
    if created:
        Notification.objects.create(kind="friend request", recipient=recipient, actor=request.user)
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "request_id": obj.pk})
    flash_messages.success(request, "Friend request sent.")
    return redirect("profile", user_id=recipient.pk)

@login_required
@require_POST
def respond_friend_request(request, request_id, decision):
    item = get_object_or_404(FriendRequest, pk=request_id, recipient=request.user, status="pending")
    if decision not in ("accept", "reject"): return JsonResponse({"error": "Unknown decision."}, status=400)
    item.status = "accepted" if decision == "accept" else "rejected"; item.save(update_fields=["status"])
    if decision == "accept":
        left, right = sorted((item.sender_id, item.recipient_id))
        Friendship.objects.get_or_create(user1_id=left, user2_id=right)
        Notification.objects.create(kind="friend request accepted", recipient=item.sender, actor=request.user)
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "status": item.status})
    flash_messages.success(request, "Friend request %s." % item.status)
    return redirect("friends")

@login_required
def friends(request):
    ids = []
    for friendship in Friendship.objects.filter(models.Q(user1=request.user) | models.Q(user2=request.user)):
        ids.append(friendship.user2_id if friendship.user1_id == request.user.id else friendship.user1_id)
    return render(request, "tabi/friends.html", {"friends": User.objects.filter(id__in=ids), "requests": FriendRequest.objects.filter(recipient=request.user, status="pending")})

@login_required
@require_POST
def block_user(request, user_id):
    member = get_object_or_404(User, pk=user_id)
    if member == request.user: return JsonResponse({"error": "You cannot block yourself."}, status=400)
    BlockedUser.objects.get_or_create(blocker=request.user, blocked=member)
    Follow.objects.filter(user__in=[request.user, member], user_follower__in=[request.user, member]).delete()
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    flash_messages.success(request, "This member has been blocked.")
    return redirect("profile", user_id=member.pk)

@login_required
@require_POST
def remove_community_post(request, slug, post_id):
    community = get_object_or_404(Community, slug=slug)
    if not CommunityMembership.objects.filter(community=community, user=request.user, role__in=["owner", "moderator"]).exists(): return HttpResponseForbidden("Community moderators only.")
    post = get_object_or_404(Post, pk=post_id, community=community); post.delete()
    return redirect("community", slug=slug)

@login_required
def personal_feed(request):
    # Documented ranking weights: TF-IDF similarity .65, recency .20,
    # followed-author/community relationship .15. Popularity is never used.
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    WEIGHTS = {"similarity": 0.65, "recency": 0.20, "relationship": 0.15}
    profile = Profile.objects.filter(user=request.user).first()
    interest_names = list(profile.interests.values_list("name", flat=True)) if profile else []
    liked_text = Post.objects.filter(likes=request.user).values_list("content", flat=True)
    commented_text = Post.objects.filter(comments__user=request.user).values_list("content", flat=True)
    followed_ids = Follow.objects.filter(user=request.user).values_list("user_follower_id", flat=True)
    community_ids = CommunityMembership.objects.filter(user=request.user).values_list("community_id", flat=True)
    hidden_ids = BlockedUser.objects.filter(models.Q(blocker=request.user) | models.Q(blocked=request.user)).values_list("blocker_id", "blocked_id")
    blocked = {user_id for pair in hidden_ids for user_id in pair if user_id != request.user.id}
    qs = list(Post.objects.exclude(user_id__in=blocked).select_related("user", "community").prefetch_related("hashtags", "community__interests").order_by("-date"))
    if not qs: return render(request, "tabi/feed.html", {"posts_of_the_page": []})
    interest_doc = " ".join(interest_names + list(liked_text) + list(commented_text))
    docs = [interest_doc or "shared discoveries"] + [p.content + " " + " ".join(h.name for h in p.hashtags.all()) + (" " + p.community.name if p.community_id else "") for p in qs]
    try:
        vectors = TfidfVectorizer(stop_words="english").fit_transform(docs)
        similarities = cosine_similarity(vectors[0:1], vectors[1:]).flatten()
    except ValueError:
        similarities = [0.0] * len(qs)
    now = timezone.now(); scored = []
    interest_vocab = {name.lower() for name in interest_names}
    for post, similarity in zip(qs, similarities):
        age_days = max(0, (now - post.date).total_seconds() / 86400)
        recency = 1 / (1 + age_days / 7)
        followed = post.user_id in followed_ids
        community_match = post.community_id in community_ids
        relationship = 1.0 if followed or community_match else 0.0
        score = WEIGHTS["similarity"] * float(similarity) + WEIGHTS["recency"] * recency + WEIGHTS["relationship"] * relationship
        tags = {tag.name.lower() for tag in post.hashtags.all()}
        matched = sorted(interest_vocab.intersection(tags))
        post.feed_reason = ("matches your interest in " + matched[0]) if matched else ("from someone you follow" if followed else ("from a community you joined" if community_match else "a recent post, matched to your discoveries"))
        scored.append((score, post))
    scored.sort(key=lambda item: (item[0], item[1].date), reverse=True)
    profile = Profile.objects.filter(user=request.user).first()
    suggestions = User.objects.filter(profile__interests__in=profile.interests.all(), status="active").exclude(pk=request.user.pk).distinct()[:4] if profile and profile.interests.exists() else []
    return render(request, "tabi/feed.html", {"posts_of_the_page": _page(request, [item[1] for item in scored]), "profile": profile, "curiosities": profile.interests.all()[:5] if profile else [], "streak": Streak.objects.filter(user=request.user).order_by("-current").first(), "suggestions": suggestions})

@login_required
@require_POST
def report_post(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    reason = request.POST.get("reason", "").strip()[:300]
    if not reason: return JsonResponse({"error": "Please provide a reason."}, status=400)
    from django.conf import settings
    configured_words = getattr(settings, "TABI_FLAG_WORDS", ("buy now", "free money", "click here"))
    keyword_hit = any(word.lower() in post.content.lower() for word in configured_words)
    repeated = bool(re.search(r"(.{8,})\1{2,}", post.content.lower()))
    auto = keyword_hit or repeated
    Report.objects.create(reporter=request.user, post=post, reason=reason, auto_flagged=auto)
    return JsonResponse({"ok": True})

@login_required
@require_POST
def report_comment(request, comment_id):
    item = get_object_or_404(Comment, pk=comment_id)
    reason = request.POST.get("reason", "").strip()[:300]
    if not reason: return JsonResponse({"error": "Please provide a reason."}, status=400)
    Report.objects.create(reporter=request.user, comment=item, reason=reason, auto_flagged=bool(re.search(r"(buy now|free money|click here){2,}", item.content.lower())))
    return JsonResponse({"ok": True})

@login_required
@require_POST
def report_user(request, user_id):
    member = get_object_or_404(User, pk=user_id)
    reason = request.POST.get("reason", "").strip()[:300]
    if member == request.user or not reason: return JsonResponse({"error": "Choose another user and provide a reason."}, status=400)
    Report.objects.create(reporter=request.user, reported_user=member, reason=reason)
    return JsonResponse({"ok": True})

@staff_member_required
def export_csv(request, kind):
    if kind not in {"users", "posts", "reports"}: return JsonResponse({"error": "Choose users, posts, or reports."}, status=400)
    response = HttpResponse(content_type="text/csv"); response["Content-Disposition"] = 'attachment; filename="tabi-%s.csv"' % kind
    if kind == "users":
        rows = list(User.objects.values("id", "username", "status", "date_joined"))
    elif kind == "posts":
        rows = list(Post.objects.values("id", "user__username", "is_anonymous", "content", "date"))
    else:
        rows = list(Report.objects.values("id", "reporter__username", "reason", "status", "auto_flagged", "created_at"))
    import pandas as pd
    response.write(pd.DataFrame(rows).to_csv(index=False))
    return response

@staff_member_required
def export_pdf(request):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from io import BytesIO
    output = BytesIO(); pdf = canvas.Canvas(output, pagesize=letter)
    pdf.drawString(50, 750, "Tabi activity and moderation report")
    pdf.drawString(50, 725, "Generated: %s" % timezone.localtime().strftime("%Y-%m-%d %H:%M"))
    pdf.drawString(50, 690, "Users: %s" % User.objects.count())
    pdf.drawString(50, 670, "Posts: %s" % Post.objects.count())
    pdf.drawString(50, 650, "Pending reports: %s" % Report.objects.filter(status="pending").count())
    pdf.save(); response = HttpResponse(output.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="tabi-activity.pdf"'; return response
