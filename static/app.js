const refreshButton = document.getElementById("refreshButton");
const resultsContainer = document.getElementById("analysisResults");
const goalInput = document.getElementById("goal");

function escapeHTML(value) {
    return String(value).replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    })[character]);
}

async function loadLatestAnalysis() {
    resultsContainer.innerHTML = `
        <div class="empty-state">
            <div>⏳</div>
            <h3>Loading your analysis...</h3>
            <p>Please wait while TabMind retrieves your latest results.</p>
        </div>
    `;

    try {
        const response = await fetch("/api/latest");
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Unable to load analysis.");
        }

        if (data.message) {
            resultsContainer.innerHTML = `
                <div class="empty-state">
                    <div>📊</div>
                    <h3>No analysis available yet</h3>
                    <p>Use the TabMind Chrome extension to analyse your browser tabs.</p>
                </div>
            `;
            return;
        }

        displayAnalysis(data);

    } catch (error) {
        resultsContainer.innerHTML = `
            <div class="empty-state">
                <div>⚠️</div>
                <h3>Unable to load results</h3>
                <p>${escapeHTML(error.message)}</p>
            </div>
        `;
    }
}

function displayAnalysis(data) {
    goalInput.value = data.goal || "";

    const tabs = data.tabs || [];
    const distractingIds = data.distracting_tab_ids || [];
    const summaries = data.summary_bullets || [];

    const distractingTabs = tabs.filter(tab =>
        distractingIds.includes(tab.id)
    );

    const relevantTabs = tabs.filter(tab =>
        !distractingIds.includes(tab.id)
    );

    resultsContainer.innerHTML = `
        <div class="analysis-overview">

            <h3>🎯 Your Focus Goal</h3>
            <p>${escapeHTML(data.goal || "No goal provided")}</p>

            <div class="analysis-stats">
                <div>
                    <strong>${tabs.length}</strong>
                    <span>Total Tabs</span>
                </div>

                <div>
                    <strong>${relevantTabs.length}</strong>
                    <span>Relevant Tabs</span>
                </div>

                <div>
                    <strong>${distractingTabs.length}</strong>
                    <span>Distractions</span>
                </div>
            </div>

        </div>

        <div class="analysis-section">
            <h3>📚 Your 5 Research Insights</h3>

            <div class="summary-list">
                ${
                    summaries.length
                    ? summaries.map((item, index) => `
                        <div class="summary-item">
                            <span>${index + 1}</span>
                            <p>${escapeHTML(item)}</p>
                        </div>
                    `).join("")
                    : "<p>No research insights were returned.</p>"
                }
            </div>
        </div>

        <div class="analysis-section">
            <h3>⚡ Distracting Tabs</h3>

            ${
                distractingTabs.length
                ? distractingTabs.map(tab => `
                    <div class="tab-item">
                        <div>
                            <strong>${escapeHTML(tab.title || "Untitled tab")}</strong>
                            <small>${escapeHTML(tab.url || "")}</small>
                        </div>
                        <span class="distraction-label">Distraction</span>
                    </div>
                `).join("")
                : "<p>No distracting tabs identified.</p>"
            }
        </div>

        <div class="analysis-section">
            <h3>✅ Relevant Tabs</h3>

            ${
                relevantTabs.length
                ? relevantTabs.map(tab => `
                    <div class="tab-item">
                        <div>
                            <strong>${escapeHTML(tab.title || "Untitled tab")}</strong>
                            <small>${escapeHTML(tab.url || "")}</small>
                        </div>
                        <span class="relevant-label">Relevant</span>
                    </div>
                `).join("")
                : "<p>No relevant tabs identified.</p>"
            }
        </div>

        <p class="results-note">
            Analysis provided by TabMind AI. Review your results before closing any tabs.
        </p>
    `;
}

refreshButton.addEventListener("click", loadLatestAnalysis);

loadLatestAnalysis();
