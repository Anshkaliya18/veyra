document.addEventListener("DOMContentLoaded", () => {
    loadTimeline();

    const searchInput = document.getElementById("timelineSearch");
    const categoryFilter = document.getElementById("timelineFilter");

    if (searchInput) {
        searchInput.addEventListener("input", filterTimeline);
    }

    if (categoryFilter) {
        categoryFilter.addEventListener("change", filterTimeline);
    }
});

let allEvents = [];

async function loadTimeline() {

    const container = document.getElementById("timelineContainer");
    const stats = document.getElementById("timelineStats");

    container.innerHTML = `
        <div class="loading">
            Loading timeline...
        </div>
    `;

    try {

        const res = await fetch("/api/timeline");

        if (!res.ok)
            throw new Error("Unable to fetch timeline.");

        const data = await res.json();

        if (!data.success) {
            throw new Error("Timeline generation failed.");
        }

        allEvents = data.events || [];

        if (stats && data.stats) {
            stats.textContent =
                `${data.stats.total} milestones • ${data.stats.years} years`;
        }

        renderTimeline(allEvents);

    } catch (err) {

        console.error(err);

        container.innerHTML = `
            <div class="empty-state">
                <h2>No Timeline</h2>
                <p>${err.message}</p>
            </div>
        `;
    }
}

function renderTimeline(events) {

    const container = document.getElementById("timelineContainer");

    container.innerHTML = "";

    if (!events.length) {

        container.innerHTML = `
            <div class="empty-state">
                <h2>No timeline events</h2>
            </div>
        `;

        return;
    }

    let currentYear = "";

    events.forEach(event => {

        if (event.year !== currentYear) {

            currentYear = event.year;

            container.insertAdjacentHTML(
                "beforeend",
                `
                <div class="timeline-year">
                    ${currentYear}
                </div>

                <div class="timeline-group"
                     id="year-${currentYear}">
                </div>
                `
            );
        }

        const yearContainer =
            document.getElementById(`year-${currentYear}`);

        yearContainer.insertAdjacentHTML(
            "beforeend",
            `
            <article class="timeline-card"
                     data-category="${event.category}"
                     data-title="${escapeHtml(event.title)}">

                <div class="timeline-header">

                    <span class="timeline-category">
                        ${icon(event.category)}
                        ${escapeHtml(event.category)}
                    </span>

                    <span class="timeline-date">
                        ${escapeHtml(event.display_date || event.date)}
                    </span>

                </div>

                <h3>
                    ${escapeHtml(event.title)}
                </h3>

                <p>
                    ${escapeHtml(event.description)}
                </p>

                <div class="timeline-tags">

                    ${(event.tags || []).map(tag => `
                        <span>${escapeHtml(tag)}</span>
                    `).join("")}

                </div>

            </article>
            `
        );

    });

}

function filterTimeline() {

    const search =
        document.getElementById("timelineSearch")?.value.toLowerCase() || "";

    const category =
        document.getElementById("timelineFilter")?.value || "";

    const filtered = allEvents.filter(event => {

        const matchesSearch =
            event.title.toLowerCase().includes(search) ||
            event.description.toLowerCase().includes(search);

        const matchesCategory =
            !category || event.category === category;

        return matchesSearch && matchesCategory;

    });

    renderTimeline(filtered);

}

function icon(category) {

    switch(category){

        case "Project":
            return "🚀";

        case "Education":
            return "🎓";

        case "Experience":
            return "💼";

        case "Achievement":
            return "🏆";

        case "Credential":
            return "📜";

        case "Research":
            return "📖";

        case "Skill":
            return "🛠️";

        default:
            return "📌";

    }

}

function escapeHtml(text){

    if(!text)
        return "";

    return String(text)
        .replace(/&/g,"&amp;")
        .replace(/</g,"&lt;")
        .replace(/>/g,"&gt;")
        .replace(/"/g,"&quot;")
        .replace(/'/g,"&#039;");

}