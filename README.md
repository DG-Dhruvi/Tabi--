# Tabi 旅

**A community for meaningful connection.** Tabi means journey in Japanese: a place to discover people through shared interests and hobbies rather than popularity.

> A journey is not measured by the distance travelled, but by what is discovered along the way.

Full Stack Development Lab · JIIT Noida

## Features

- Django authentication, profiles, optional profile images, bios, location, and selectable interests.
- Posts, comments, likes, hashtag pages, edit-own-post AJAX, and a chronological Following feed.
- Anonymous posts and comments show an anonymous label to members; the user link is available only to staff in Django Admin.
- Follow/unfollow and shared-interest suggestions; communities with memberships and role fields.
- Participant-checked conversations with four-second Fetch polling, search JSON, and in-app notifications.
- Interest-oriented feed with an explanation on each card; like and follower counts never affect ranking.
- Reports, review queues, account status controls, admin CSV exports, and an activity PDF.
- Gentle per-interest streak tracking. There are no Stories or expiry features.

## Architecture and data model

This is a Django MVT application. The `tabi` package uses its established database migration label to preserve existing user records and migration history. Core accounts, posts, likes, follows, communities, messaging, and moderation are organized within the Tabi app. Existing login, profiles, the Following route, and ten-item pagination are retained.

Core relationships: `User` has one `Profile` and optional `AnonymousProfile`; `Profile` selects many `Interest`s. `Post` belongs to a user and optionally a `Community`, with many `Hashtag`s; `Comment` and likes belong to posts. `CommunityMembership` joins users to communities with roles. `Conversation` has participant users and many `Message`s. `Notification` and `Report` reference users and relevant content. `Streak` is unique per user and interest.

```text
User ──1:1── Profile ──M:N── Interest ──1:M── Streak
  │             └── optional profile image
  ├──1:1── AnonymousProfile (staff-only identity link)
  ├──1:M── Post ──M:N── Hashtag
  │           ├──1:M── Comment
  │           └──M:1── Community ──M:N── CommunityMembership ──M:1── User
  └──M:N── Conversation ──1:M── Message
```

## Setup

Requires Python 3.10+.

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. Use the superuser credentials you created for admin moderation. To create demo content, run `python manage.py seed_demo_data`; it creates `demo_mika`, `demo_ren`, and `demo_aki`, each with password `TabiDemo2026!`. Change or delete these sample accounts before any public deployment.

## Feed ranking

The feed builds a user-interest document from declared interests and text from liked/commented posts, then uses scikit-learn TF-IDF vectors and cosine similarity against candidate post text and hashtags. It combines similarity (0.65), seven-day recency decay (0.20), and a followed-author/community membership boost (0.15). Each card gives a short explanation. Likes and follower counts are not ranking signals. The model is intentionally lightweight and content-based.

## Limitations

- Messaging uses periodic AJAX polling, not WebSockets.
- Content recommendations use basic tag matching rather than a trained or semantic model.
- Automatic flagging is a simple review hint; it never bans accounts.
- SQLite is the configured development database; no PostgreSQL deployment has been verified.
- PDF/CSV reports are basic administrative summaries.
- The app is web-only. It is a university project, not a secure channel for sensitive information.

## Privacy and ethics

Anonymous posting hides identity from other members, but authorized staff can trace it during moderation. Users should not include personal details in anonymous content. Tabi avoids popularity-based feed ranking and urgency messaging. Review the in-app [Privacy & Ethics page](/privacy).
