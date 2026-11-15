import json
from django.test import TestCase
from django.urls import reverse
from .models import User, Post, Conversation, Message, Interest, Profile, Hashtag

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

    def test_nonparticipant_cannot_poll_conversation(self):
        thread = Conversation.objects.create(); thread.participants.add(self.alice, self.bob)
        self.client.force_login(User.objects.create_user("outsider", password="Pass12345!"))
        response = self.client.get(reverse("poll_messages", args=[thread.pk]))
        self.assertEqual(response.status_code, 404)

    def test_anonymous_search_does_not_return_account_link(self):
        self.post.is_anonymous = True; self.post.save()
        response = self.client.get(reverse("search"), {"q": "discovery"})
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

