const API_URL = "https://tabmind-rd6e.onrender.com";

const goalInput = document.getElementById("goal");
const tabCount = document.getElementById("tabCount");
const analyzeButton = document.getElementById("analyzeButton");
const message = document.getElementById("message");
const results = document.getElementById("results");
const summary = document.getElementById("summary");
const distractions = document.getElementById("distractions");
const closeButton = document.getElementById("closeButton");

let distractingTabs = [];

async function updateTabCount() {
    const tabs = await chrome.tabs.query({});
    tabCount.textContent = tabs.length;
}

function showMessage(text) {
    message.textContent = text;
}


// Extract readable text from a webpage
async function extractPageContent(tabId) {
    try {
        const result = await chrome.scripting.executeScript({
            target: { tabId },
            func: () => {
                return (document.body?.innerText || "")
                    .replace(/\s+/g, " ")
                    .trim()
                    .slice(0, 6000);
            }
        });

        return result[0]?.result || "";

    } catch (error) {
        return "";
    }
}


// Analyse browser tabs
analyzeButton.addEventListener("click", async () => {

    const goal = goalInput.value.trim();

    if (!goal) {
        showMessage("Please enter your focus goal first.");
        return;
    }

    analyzeButton.disabled = true;
    analyzeButton.textContent = "Analysing...";
    showMessage("Reading webpages and analysing your tabs...");

    results.classList.add("hidden");

    try {

        const tabs = await chrome.tabs.query({});

        const browserTabs = tabs.filter(tab =>
            tab.id &&
            tab.url &&
            (tab.url.startsWith("http://") ||
                tab.url.startsWith("https://"))
        );

        if (browserTabs.length === 0) {
            throw new Error("No accessible webpages found.");
        }

        const cleanTabs = [];

        for (const tab of browserTabs) {

            showMessage(`Reading: ${tab.title || "Webpage"}...`);

            const content = await extractPageContent(tab.id);

            cleanTabs.push({
                id: tab.id,
                title: tab.title || "Untitled tab",
                url: tab.url,
                content: content || "Page content unavailable."
            });
        }

        showMessage("Sending webpage information to Gemini AI...");

        const response = await fetch(`${API_URL}/api/analyze`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                goal: goal,
                tabs: cleanTabs
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.details || data.error || "Analysis failed.");
        }

        displayResults(data);

        showMessage("AI analysis completed successfully!");

    } catch (error) {

        showMessage(error.message);

    } finally {

        analyzeButton.disabled = false;
        analyzeButton.textContent = "✨ Analyse My Tabs";

    }
});


// Display AI results
function displayResults(data) {

    results.classList.remove("hidden");

    summary.innerHTML = "";
    distractions.innerHTML = "";

    distractingTabs = data.tabs.filter(tab =>
        data.distracting_tab_ids.includes(tab.id)
    );

    data.summary_bullets.forEach((item, index) => {

        const div = document.createElement("div");
        div.className = "summary-item";

        const number = document.createElement("span");
        number.textContent = index + 1;

        const text = document.createElement("p");
        text.textContent = item;

        div.append(number, text);
        summary.appendChild(div);

    });

    distractingTabs.forEach(tab => {

        const div = document.createElement("div");
        div.className = "distraction-item";

        const label = document.createElement("label");

        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.value = tab.id;

        const title = document.createElement("span");
        title.textContent = tab.title;

        label.append(checkbox, title);

        const url = document.createElement("small");
        url.textContent = tab.url;

        div.append(label, url);
        distractions.appendChild(div);

    });

    if (distractingTabs.length > 0) {
        closeButton.classList.remove("hidden");
    } else {
        closeButton.classList.add("hidden");

        const text = document.createElement("p");
        text.textContent = "No distracting tabs found.";
        distractions.appendChild(text);
    }
}


// Close selected tabs only after confirmation
closeButton.addEventListener("click", async () => {

    const selected = Array.from(
        distractions.querySelectorAll("input:checked")
    ).map(input => Number(input.value));

    if (selected.length === 0) {
        showMessage("Select at least one tab to close.");
        return;
    }

    const confirmed = confirm(
        `Are you sure you want to close ${selected.length} selected tab(s)?`
    );

    if (!confirmed) return;

    try {

        await chrome.tabs.remove(selected);

        showMessage(`${selected.length} selected tab(s) closed.`);

        await updateTabCount();

        closeButton.classList.add("hidden");

    } catch (error) {

        showMessage("Unable to close tabs: " + error.message);

    }
});


// Initial setup
updateTabCount();