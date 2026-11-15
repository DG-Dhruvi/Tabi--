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

            contentDiv.innerHTML = `
                <textarea class="edit-textarea">${oldContent}</textarea>
                <button class="save-button">Save</button>
            `;

            post.querySelector(".save-button").addEventListener("click", function () {

                const newContent =
                    post.querySelector(".edit-textarea").value;

                fetch(`/editPost/${postId}`, {
                    method: "POST",

                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": getCookie("csrftoken")
                    },

                    body: JSON.stringify({
                        content: newContent
                    })
                })

                .then(response => response.json())

                .then(data => {

                    if (data.error) {
                        alert(data.error);
                        return;
                    }

                    contentDiv.innerText = data.content;

                    // Show Edit button again
                    button.style.display = "inline-block";

                });

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

            fetch(`/like/${postId}`, {

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

            .catch(error => {

                console.log("LIKE ERROR:", error);

                alert("Something went wrong while liking the post.");

            });

        });

    });

    document.querySelectorAll(".comment-form, .report-form").forEach(form => {
        form.addEventListener("submit", async event => {
            event.preventDefault();
            const response = await fetch(form.dataset.url, {method: "POST", headers: {"X-CSRFToken": getCookie("csrftoken")}, body: new FormData(form)});
            const result = await response.json();
            if (!response.ok) { alert(result.error || "Could not submit this form."); return; }
            if (form.classList.contains("comment-form")) {
                const p = document.createElement("p"); p.textContent = `${result.author}: ${result.content}`;
                form.parentElement.querySelector(".comments").appendChild(p); form.reset();
            } else { form.innerHTML = "<span>Thank you. Your report was sent for review.</span>"; }
        });
    });

    const search = document.querySelector("#site-search");
    if (search) {
        let timer;
        search.addEventListener("input", () => {
            clearTimeout(timer); timer = setTimeout(async () => {
                const response = await fetch(`/search?q=${encodeURIComponent(search.value)}`);
                const results = await response.json(); const list = document.querySelector("#search-results"); list.replaceChildren();
                Object.entries(results).forEach(([kind, entries]) => entries.forEach(item => {
                    const row = document.createElement("div");
                    row.textContent = `${kind}: ${item.username || item.name || item.content || ""}`; list.appendChild(row);
                }));
            }, 250);
        });
    }

    document.querySelectorAll("[data-poll-url]").forEach(container => {
        let lastId = Number(container.dataset.lastId || 0);
        setInterval(async () => {
            const response = await fetch(`${container.dataset.pollUrl}?after=${lastId}`);
            if (!response.ok) return;
            const data = await response.json();
            data.messages.forEach(item => { const p = document.createElement("p"); p.textContent = `${item.sender__username}: ${item.content}`; container.appendChild(p); lastId = Math.max(lastId, item.id); });
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
