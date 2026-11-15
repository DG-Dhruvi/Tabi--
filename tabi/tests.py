import json
from io import BytesIO
import tempfile
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.test import TestCase
from django.urls import reverse
from .models import User, Post, Conversation, Message, Interest, Profile, Hashtag, FriendRequest, Friendship, Community, CommunityMembership, Comment, Notification

class TabiCoreTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="Pass12345!")
        self.bob = User.objects.create_user("bob", password="Pass12345!")
        self.post = Post.objects.create(user=self.alice, content="A small discovery")

    def test_user_cannot_edit_another_users_post(self):
        self.client.force_login(self.bob)
        response = self.client.post(reverse("editPost", args=[self.post.pk]), data=json.dumps({"content": "changed"}), content_type="application/json")
        self.assertEqual(response.status_code, 403)
        self.post.refresh_from_db(); self.assertEqual(self.post.content, "A small discovery")

    def test_profile_edit_offers_interests_and_saves_custom_interests(self):
        self.client.force_login(self.alice)
        page = self.client.get(reverse("edit_profile"))
        self.assertContains(page, "Photography")
        self.assertContains(page, "Add your own interests")
        photography = Interest.objects.get(slug="photography")
        saved = self.client.post(reverse("edit_profile"), {
            "bio": "Noticing small things", "location": "Noida",
            "interests": [photography.pk], "custom_interests": "Hiking, Film photography",
        })
        self.assertEqual(saved.status_code, 302)
        profile = Profile.objects.get(user=self.alice)
        self.assertEqual(set(profile.interests.values_list("name", flat=True)), {"Photography", "Hiking", "Film photography"})
        self.assertEqual(profile.bio, "Noticing small things")

    def test_profile_tabs_and_friend_request_acceptance_are_reachable(self):
        self.client.force_login(self.alice)
        profile_page = self.client.get(reverse("profile", args=[self.alice.pk]))
        self.assertContains(profile_page, 'href="#about"')
        self.assertContains(profile_page, 'href="#profile-connections"')
        self.assertContains(profile_page, 'href="#saved"')
        self.assertContains(profile_page, 'id="saved-moments-list"')
        self.assertContains(profile_page, 'href="/friends"')
        request = FriendRequest.objects.create(sender=self.bob, recipient=self.alice)
        friends_page = self.client.get(reverse("friends"))
        self.assertContains(friends_page, "Accept")
        accepted = self.client.post(reverse("respond_friend_request", args=[request.pk, "accept"]))
        self.assertEqual(accepted.status_code, 302)
        self.assertTrue(Friendship.objects.filter(user1=self.alice, user2=self.bob).exists() or Friendship.objects.filter(user1=self.bob, user2=self.alice).exists())

    def test_profile_photo_upload_renders_in_account_and_profile(self):
        image_file = BytesIO()
        Image.new("RGB", (2, 2), color="green").save(image_file, format="PNG")
        self.client.force_login(self.alice)
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            saved = self.client.post(reverse("edit_profile"), {
                "bio": "A new photo", "location": "Noida", "custom_interests": "",
                "picture": SimpleUploadedFile("portrait.png", image_file.getvalue(), content_type="image/png"),
            })
            self.assertEqual(saved.status_code, 302, saved.context["form"].errors if saved.context else saved.content.decode()[:1000])
            profile = Profile.objects.get(user=self.alice)
            self.assertTrue(profile.picture.name)
            page = self.client.get(reverse("profile", args=[self.alice.pk]))
            self.assertContains(page, profile.picture.url)

    def test_edit_page_is_owner_only_and_updates_post(self):
        self.client.force_login(self.bob)
        denied = self.client.get(reverse("edit_post_page", args=[self.post.pk]))
        self.assertEqual(denied.status_code, 403)
        self.client.force_login(self.alice)
        page = self.client.get(reverse("edit_post_page", args=[self.post.pk]))
        self.assertEqual(page.status_code, 200)
        saved = self.client.post(reverse("edit_post_page", args=[self.post.pk]), {"content": "A clearer thought"})
        self.assertEqual(saved.status_code, 302)
        self.post.refresh_from_db(); self.assertEqual(self.post.content, "A clearer thought")

    def test_nonparticipant_cannot_poll_conversation(self):
        thread = Conversation.objects.create(); thread.participants.add(self.alice, self.bob)
        self.client.force_login(User.objects.create_user("outsider", password="Pass12345!"))
        response = self.client.get(reverse("poll_messages", args=[thread.pk]))
        self.assertEqual(response.status_code, 404)

    def test_anonymous_search_does_not_return_account_link(self):
        self.post.is_anonymous = True; self.post.save()
        response = self.client.get(reverse("search"), {"q": "discovery"}, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["posts"][0]["author"], "Anonymous member")
        self.assertNotIn("alice", response.content.decode())

    def test_feed_prefers_matching_interests_without_popularity(self):
        profile, _ = Profile.objects.get_or_create(user=self.alice)
        interest = Interest.objects.create(name="Photography", slug="photography")
        profile.interests.add(interest)
        matching = Post.objects.create(user=self.bob, content="A photo #photography")
        tag = Hashtag.objects.create(name="photography"); matching.hashtags.add(tag)
        self.client.force_login(self.alice)
        response = self.client.get(reverse("personal_feed"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "matches your interest in photography")

    def test_profile_edit_saves_and_redirects_with_success_message(self):
        self.client.force_login(self.alice)
        response = self.client.post(reverse("edit_profile"), {"bio": "I like quiet walks", "location": "Noida", "interests": []})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("profile", args=[self.alice.pk]))
        self.alice.profile.refresh_from_db()
        self.assertEqual(self.alice.profile.bio, "I like quiet walks")
        self.assertContains(self.client.get(response.url), "Your profile is updated.")

    def test_friend_request_form_redirects_instead_of_showing_raw_json(self):
        self.client.force_login(self.alice)
        response = self.client.post(reverse("send_friend_request", args=[self.bob.pk]))
        self.assertRedirects(response, reverse("profile", args=[self.bob.pk]))
        self.assertTrue(FriendRequest.objects.filter(sender=self.alice, recipient=self.bob, status="pending").exists())

    def test_ajax_friend_request_returns_json_and_can_be_accepted(self):
        self.client.force_login(self.alice)
        request = self.client.post(reverse("send_friend_request", args=[self.bob.pk]), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(request.status_code, 200)
        request_id = request.json()["request_id"]
        self.client.force_login(self.bob)
        accepted = self.client.post(reverse("respond_friend_request", args=[request_id, "accept"]), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(accepted.json()["status"], "accepted")
        self.assertTrue(self.client.get(reverse("profile", args=[self.alice.pk])).status_code == 200)

    def test_messages_and_friends_pages_render(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(reverse("messages")).status_code, 200)
        self.assertEqual(self.client.get(reverse("friends")).status_code, 200)
        thread = Conversation.objects.create(); thread.participants.add(self.alice, self.bob)
        self.assertEqual(self.client.get(reverse("messages")).status_code, 200)

    def test_conversation_list_form_uses_username_and_reuses_thread(self):
        self.client.force_login(self.alice)
        response = self.client.post(reverse("messages"), {"username": self.bob.username})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Conversation.objects.get().participants.count(), 2)
        self.client.post(reverse("messages"), {"username": self.bob.username})
        self.assertEqual(Conversation.objects.count(), 1)

    def test_conversation_and_notification_pages_render(self):
        thread = Conversation.objects.create(); thread.participants.add(self.alice, self.bob)
        Message.objects.create(conversation=thread, sender=self.bob, content="Hello")
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(reverse("conversation", args=[thread.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("notifications")).status_code, 200)

    def test_community_pages_render(self):
        community = Community.objects.create(name="Walkers", slug="walkers", description="A group", created_by=self.alice)
        CommunityMembership.objects.create(community=community, user=self.alice, role="owner")
        Post.objects.create(user=self.alice, content="A photo walk", community=community, image="posts/walk.png")
        self.client.force_login(self.alice)
        communities_page = self.client.get(reverse("communities"))
        discover_page = self.client.get(reverse("discover"))
        self.assertEqual(communities_page.status_code, 200)
        self.assertEqual(discover_page.status_code, 200)
        self.assertTemplateUsed(communities_page, "tabi/communities.html")
        self.assertTemplateUsed(discover_page, "tabi/discover.html")
        self.assertContains(communities_page, "Spaces you belong to")
        self.assertContains(discover_page, "FOLLOW YOUR CURIOSITY")
        community_page = self.client.get(reverse("community", args=[community.slug]))
        self.assertEqual(community_page.status_code, 200)
        self.assertContains(community_page, 'href="#photo-journal"')
        self.assertContains(community_page, 'id="photo-journal"')
        self.assertContains(community_page, 'id="members"')
        self.assertContains(community_page, "A photo walk")
        self.assertContains(community_page, "@alice")

    def test_explore_following_and_html_search_render(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(reverse("index")).status_code, 200)
        self.assertEqual(self.client.get(reverse("following")).status_code, 200)
        self.assertEqual(self.client.get(reverse("search"), {"q": "discovery"}).status_code, 200)

    def test_post_like_comment_and_report_json_endpoints(self):
        self.client.force_login(self.bob)
        create = self.client.post(reverse("newPost"), {"content": "A post with #camping"})
        self.assertEqual(create.status_code, 302)
        new_post = Post.objects.get(user=self.bob)
        self.assertTrue(new_post.hashtags.filter(name="camping").exists())
        liked = self.client.post(reverse("like", args=[self.post.pk]))
        self.assertEqual(liked.json(), {"liked": True, "likes": 1})
        commented = self.client.post(reverse("comment", args=[self.post.pk]), {"content": "Thank you for sharing"})
        self.assertEqual(commented.status_code, 200)
        self.assertTrue(Comment.objects.filter(post=self.post, user=self.bob).exists())
        report = self.client.post(reverse("report_post", args=[self.post.pk]), {"reason": "Needs review"})
        self.assertEqual(report.json(), {"ok": True})

    def test_unread_notification_endpoint_and_mark_read(self):
        Notification.objects.create(kind="follow", recipient=self.alice, actor=self.bob)
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(reverse("unread_notifications")).json()["unread"], 1)
        response = self.client.post(reverse("notifications"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get(reverse("unread_notifications")).json()["unread"], 0)

