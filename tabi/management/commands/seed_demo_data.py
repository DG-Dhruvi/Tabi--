from django.core.management.base import BaseCommand
from django.utils.text import slugify
from tabi.models import User, Profile, Interest, Post, Community, CommunityMembership

class Command(BaseCommand):
    help = "Create a small, repeatable Tabi demo dataset."
    def handle(self, *args, **options):
        topics = ["Photography", "Gardening", "Books"]
        interests = []
        for name in topics:
            item, _ = Interest.objects.get_or_create(slug=slugify(name), defaults={"name": name})
            interests.append(item)
        users = []
        for username in ("demo_mika", "demo_ren", "demo_aki"):
            user, created = User.objects.get_or_create(username=username, defaults={"email": username + "@example.test"})
            if created:
                user.set_password("TabiDemo2026!"); user.save()
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.interests.add(interests[len(users)])
            users.append(user)
        samples = ["A quiet walk revealed a new favorite corner of campus. #photography", "Trying a few herbs on my windowsill this week. #gardening", "What book made you stop and reread a paragraph? #books"]
        for user, content in zip(users, samples): Post.objects.get_or_create(user=user, content=content)
        community, _ = Community.objects.get_or_create(slug="slow-discoveries", defaults={"name": "Slow Discoveries", "description": "A gentle place to share small things you have noticed.", "created_by": users[0]})
        community.interests.add(*interests)
        CommunityMembership.objects.get_or_create(community=community, user=users[0], defaults={"role": "owner"})
        self.stdout.write(self.style.SUCCESS("Demo users (password TabiDemo2026!), interests, posts, and a community are ready."))
