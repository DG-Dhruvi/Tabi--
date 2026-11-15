document.addEventListener("DOMContentLoaded", function () {

    // =========================
    // EDIT POST
    // =========================

    document.querySelectorAll(".edit-button").forEach(button => {

        button.addEventListener("click", function () {

            const postId = this.dataset.postId;
            const post = document.querySelector(`#post-${postId}`);
            const contentDiv = post.querySelector(".post-content");

            const oldContent = contentDiv.innerText;

            // Hide Edit button
            this.style.display = "none";

            const editor = document.createElement("div"); editor.className = "edit-tools";
            const textarea = document.createElement("textarea"); textarea.className = "edit-textarea"; textarea.maxLength = 500; textarea.value = oldContent;
            const save = document.createElement("button"); save.className = "save-button"; save.type = "button"; save.textContent = "Save";
            const cancel = document.createElement("button"); cancel.className = "cancel-edit"; cancel.type = "button"; cancel.textContent = "Cancel";
            editor.append(textarea, save, cancel); contentDiv.replaceChildren(editor);
            cancel.addEventListener("click", () => { contentDiv.textContent = oldContent; button.style.display = "inline-block"; });

            save.addEventListener("click", async function () {

                try {
                    const response = await fetch(`/editPost/${postId}`, {
                    method: "POST",

                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": getCookie("csrftoken")
                    },

                    body: JSON.stringify({content: textarea.value})
                    });
                    const data = await response.json();
                    if (!response.ok) throw new Error(data.error || "Could not save this post.");
                    contentDiv.textContent = data.content; button.style.display = "inline-block";
                } catch (error) { alert(error.message || "Could not save this post."); }

            });

        });

    });


    // =========================
    // LIKE / UNLIKE
    // =========================

    document.querySelectorAll(".like-button").forEach(button => {

        button.addEventListener("click", function () {

            const postId = this.dataset.postId;

            const post = document.querySelector(`#post-${postId}`);

            const likeCount =
                post.querySelector(".like-count");

            fetch(this.dataset.url || `/like/${postId}`, {

                method: "POST",

                headers: {
                    "X-CSRFToken": getCookie("csrftoken")
                }

            })

            .then(response => {

                console.log("Like response status:", response.status);

                if (!response.ok) {
                    throw new Error(
                        "Server returned " + response.status
                    );
                }

                return response.json();

            })

            .then(data => {

                console.log("Like response:", data);

                if (data.error) {
                    alert(data.error);
                    return;
                }

                // Update number of likes
                likeCount.innerText = data.likes;

                // Change Like / Unlike button
                if (data.liked) {

                    button.innerText = "Unlike";

                } else {

                    button.innerText = "Like";

                }

            })

            .catch(error => { alert(error.message || "Something went wrong while liking the post."); });

        });

    });

    document.querySelectorAll(".comment-form, .report-form").forEach(form => {
        form.addEventListener("submit", async event => {
            event.preventDefault();
            const button = form.querySelector("button[type=submit]");
            if (button) { button.disabled = true; button.dataset.label = button.textContent; button.textContent = "Sending…"; }
            try {
                const response = await fetch(form.dataset.url, {method: "POST", headers: {"X-CSRFToken": getCookie("csrftoken")}, body: new FormData(form)});
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || "Could not submit this form.");
                if (form.classList.contains("comment-form")) {
                    const p = document.createElement("p"); p.textContent = `${result.author}: ${result.content}`;
                    form.parentElement.querySelector(".comments").appendChild(p); form.reset();
                } else {
                    const done = document.createElement("span"); done.className = "form-success"; done.textContent = "Thanks. Your report was sent for review.";
                    form.replaceWith(done);
                }
            } catch (error) {
                alert(error.message || "Connection problem. Please try again.");
                if (button) { button.disabled = false; button.textContent = button.dataset.label; }
            }
        });
    });

    document.querySelectorAll(".friend-request-form").forEach(form => {
        form.addEventListener("submit", async event => {
            event.preventDefault();
            const button = form.querySelector("button"); button.disabled = true; button.textContent = "Sending…";
            try {
                const response = await fetch(form.action, {method: "POST", headers: {"X-CSRFToken": getCookie("csrftoken"), "X-Requested-With": "XMLHttpRequest"}, body: new FormData(form)});
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || "Could not send the request.");
                button.textContent = result.status === "friends" ? "Friends" : result.status === "already friends" ? "Already friends" : "Request sent";
                button.classList.add("is-confirmed");
            } catch (error) { button.disabled = false; button.textContent = "Add friend"; alert(error.message || "Connection problem. Please try again."); }
        });
    });

    document.querySelectorAll(".comment-toggle").forEach(button => {
        button.addEventListener("click", () => {
            const panel = document.getElementById(button.dataset.target);
            if (panel) panel.classList.toggle("is-open");
        });
    });

    document.querySelectorAll(".share-post").forEach(button => {
        button.addEventListener("click", async () => {
            try {
                await navigator.clipboard.writeText(button.dataset.url);
                const prior = button.textContent; button.textContent = "Copied link";
                setTimeout(() => { button.textContent = prior; }, 1800);
            } catch (_) { window.prompt("Copy this post link", button.dataset.url); }
        });
    });

    const savedItemsKey = "tabi-saved-posts";
    const readSavedItems = () => {
        try { return JSON.parse(localStorage.getItem(savedItemsKey) || "[]"); }
        catch (_) { return []; }
    };
    const savedItems = readSavedItems();
    document.querySelectorAll(".save-action").forEach(button => {
        const postId = button.dataset.postId || button.closest("[id^='post-']")?.id?.replace("post-", "");
        const saved = savedItems.some(item => String(item.id) === String(postId));
        button.textContent = saved ? "Saved" : "Save";
        button.classList.toggle("is-saved", saved);
        button.addEventListener("click", () => {
            const currentlySaved = button.classList.toggle("is-saved");
            const index = savedItems.findIndex(item => String(item.id) === String(postId));
            if (currentlySaved && index < 0) savedItems.push({
                id: postId,
                content: button.dataset.content || button.closest("[id^='post-']")?.querySelector(".post-copy")?.textContent || "",
                author: button.dataset.author || "A Tabi member",
                image: button.dataset.image || "",
                url: button.dataset.postUrl || ""
            });
            if (!currentlySaved && index >= 0) savedItems.splice(index, 1);
            localStorage.setItem(savedItemsKey, JSON.stringify(savedItems));
            button.textContent = currentlySaved ? "Saved" : "Save";
            renderSavedMoments();
        });
    });

    function renderSavedMoments() {
        const list = document.querySelector("#saved-moments-list");
        const empty = document.querySelector("#saved-moments-empty");
        if (!list) return;
        list.replaceChildren();
        const items = readSavedItems();
        if (empty) empty.hidden = items.length > 0;
        items.forEach(item => {
            const card = document.createElement("article");
            card.className = "saved-moment-card";
            const author = document.createElement("strong");
            author.textContent = item.author;
            const content = document.createElement("p");
            content.textContent = item.content;
            card.append(author, content);
            if (item.image) {
                const imageUrl = new URL(item.image, window.location.origin);
                if (imageUrl.origin === window.location.origin) {
                    const image = document.createElement("img");
                    image.src = imageUrl.href;
                    image.alt = "Saved moment";
                    card.appendChild(image);
                }
            }
            if (item.url) {
                const postUrl = new URL(item.url, window.location.origin);
                if (postUrl.origin === window.location.origin) {
                    const link = document.createElement("a");
                    link.href = postUrl.href;
                    link.textContent = "View moment";
                    card.appendChild(link);
                }
            }
            list.appendChild(card);
        });
    }
    renderSavedMoments();

    const conversationSearch = document.querySelector("#conversation-search");
    if (conversationSearch) conversationSearch.addEventListener("input", () => {
        const term = conversationSearch.value.toLowerCase();
        document.querySelectorAll(".conversation-row").forEach(row => { row.hidden = !row.textContent.toLowerCase().includes(term); });
    });

    const search = document.querySelector("#site-search");
    if (search) {
        let timer;
        search.form.addEventListener("submit", event => { event.preventDefault(); search.dispatchEvent(new Event("input")); search.focus(); });
        search.addEventListener("input", () => {
            clearTimeout(timer); timer = setTimeout(async () => {
                const list = document.querySelector("#search-results"); list.replaceChildren();
                if (!search.value.trim()) { list.classList.remove("has-results"); return; }
                try {
                    const response = await fetch(`/search?q=${encodeURIComponent(search.value)}`, {headers: {"Accept": "application/json"}});
                    const results = await response.json(); let count = 0;
                    const labels = {users: "People", posts: "Posts", hashtags: "Interests & tags", communities: "Communities"};
                    Object.entries(results).forEach(([kind, entries]) => {
                        if (!entries.length) return;
                        const heading = document.createElement("div"); heading.className = "search-group-label"; heading.textContent = labels[kind]; list.appendChild(heading);
                        entries.forEach(item => {
                            const row = document.createElement("a");
                            if (kind === "users") { row.href = `/profile/${item.id}`; row.textContent = `@${item.username}`; }
                            else if (kind === "hashtags") { row.href = `/hashtag/${encodeURIComponent(item.name)}`; row.textContent = `#${item.name}`; }
                            else if (kind === "communities") { row.href = `/communities/${encodeURIComponent(item.slug)}`; row.textContent = item.name; }
                            else { row.href = `/#post-${item.id}`; row.textContent = `${item.author}: ${item.content}`; }
                            list.appendChild(row); count++;
                        });
                    });
                    if (!count) { const empty = document.createElement("div"); empty.className = "search-empty"; empty.textContent = "No matches yet. Try another word."; list.appendChild(empty); }
                    list.classList.add("has-results");
                } catch (_) { list.classList.remove("has-results"); }
            }, 250);
        });
        search.addEventListener("focus", () => { if (search.value.trim()) document.querySelector("#search-results").classList.add("has-results"); });
        document.addEventListener("click", event => { if (!event.target.closest(".site-search")) document.querySelector("#search-results")?.classList.remove("has-results"); });
    }

    document.querySelectorAll("[data-poll-url]").forEach(container => {
        let lastId = Number(container.dataset.lastId || 0);
        setInterval(async () => {
            const response = await fetch(`${container.dataset.pollUrl}?after=${lastId}`);
            if (!response.ok) return;
            const data = await response.json();
            data.messages.forEach(item => { container.querySelector(".soft-empty")?.remove(); const p = document.createElement("p"); p.className = `message-bubble ${Number(item.sender_id) === Number(container.dataset.userId) ? "mine" : ""}`; const name = document.createElement("small"); name.textContent = Number(item.sender_id) === Number(container.dataset.userId) ? "You" : item.sender__username; const body = document.createElement("span"); body.textContent = item.content; p.append(name, body); container.appendChild(p); lastId = Math.max(lastId, item.id); });
        }, 4000);
    });

    const badge = document.querySelector("#notification-count[data-url]");
    if (badge) {
        const refreshUnread = async () => {
            const response = await fetch(badge.dataset.url);
            if (response.ok) { const data = await response.json(); badge.textContent = data.unread ? `(${data.unread})` : ""; }
        };
        refreshUnread(); setInterval(refreshUnread, 10000);
    }

});


// =========================
// CSRF COOKIE
// =========================

function getCookie(name) {

    let cookieValue = null;

    if (document.cookie && document.cookie !== "") {

        const cookies = document.cookie.split(";");

        for (let cookie of cookies) {

            cookie = cookie.trim();

            if (
                cookie.substring(0, name.length + 1)
                === name + "="
            ) {

                cookieValue = decodeURIComponent(
                    cookie.substring(name.length + 1)
                );

                break;
            }
        }
    }

    return cookieValue;
}
