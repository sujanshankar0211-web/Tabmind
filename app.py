import os
import json
import time
import urllib.request
import urllib.error

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

latest_analysis = None

GEMINI_MODEL = "gemini-3.5-flash-lite"

MAX_TABS = 25
MAX_CONTENT_LENGTH = 6000


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/health")
def health():
    return jsonify({
        "status": "online",
        "application": "TabMind",
        "ai": "Gemini"
    })


@app.route("/api/analyze", methods=["POST"])
def analyze_tabs():

    global latest_analysis

    data = request.get_json(silent=True) or {}

    goal = str(data.get("goal", "")).strip()
    tabs = data.get("tabs", [])

    if not goal:
        return jsonify({"error": "Please enter your research goal."}), 400

    if not isinstance(tabs, list) or not tabs:
        return jsonify({"error": "No browser tabs were received."}), 400

    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        return jsonify({"error": "Gemini API key is not configured."}), 500

    clean_tabs = []

    for tab in tabs[:MAX_TABS]:
        try:
            tab_id = int(tab["id"])

            if tab_id <= 0:
                continue

            url = str(tab.get("url", ""))[:500]

            clean_tabs.append({
                "id": tab_id,
                "title": str(tab.get("title", "Untitled"))[:200],
                "url": url,
                "content": str(
                    tab.get("content", "")
                )[:MAX_CONTENT_LENGTH]
            })

        except (KeyError, TypeError, ValueError):
            continue

    if not clean_tabs:
        return jsonify({"error": "No valid browser tabs were received."}), 400

    # Prepare AI instructions
    prompt = f"""
You are TabMind, an intelligent browser research assistant.

USER'S RESEARCH GOAL:
{goal}

BROWSER TABS AND EXTRACTED WEBPAGE CONTENT:
{json.dumps(clean_tabs, ensure_ascii=False)}

ANALYSIS RULES:

1. Analyse the actual webpage content.
2. Identify tabs relevant to the user's goal.
3. Identify genuinely unrelated or distracting tabs.
4. Never classify TabMind's own website or dashboard as distractions.
5. Never classify localhost or 127.0.0.1 development pages as distractions.
6. Never classify browser settings or extension pages as distractions.
7. Do not recommend closing important research pages.
8. Return only distracting tab IDs from the supplied tabs.
9. Generate exactly FIVE useful research insights.
10. Avoid repeating information.
11. Never invent facts.
12. If webpage content is unavailable, use its title and URL cautiously.

RETURN VALID JSON ONLY:

{{
    "distracting_tab_ids": [],
    "summary_bullets": [
        "Insight 1",
        "Insight 2",
        "Insight 3",
        "Insight 4",
        "Insight 5"
    ]
}}
"""

    api_url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{GEMINI_MODEL}:generateContent"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2
        }
    }

    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        },
        method="POST"
    )

    try:

        api_response = None

        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=90) as response:
                    api_response = json.loads(
                        response.read().decode("utf-8")
                    )
                break

            except urllib.error.HTTPError as error:

                error_details = error.read().decode(
                    "utf-8",
                    errors="replace"
                )

                print(
                    f"Gemini API error {error.code}:",
                    error_details
                )

                if error.code == 503 and attempt < 3:
                    wait_time = 2 ** (attempt + 1)
                    print(f"Gemini busy. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue

                if error.code == 429:
                    return jsonify({
                        "error": "Gemini API request limit reached. Please wait."
                    }), 429

                if error.code == 503:
                    return jsonify({
                        "error": "Gemini is temporarily overloaded. Please try again."
                    }), 503

                return jsonify({
                    "error": "Gemini API request failed.",
                    "details": error_details
                }), 502

        if api_response is None:
            return jsonify({"error": "Gemini did not return a response."}), 502

        result_text = (
            api_response["candidates"][0]
            ["content"]["parts"][0]["text"]
        )

        result = json.loads(result_text)

        distraction_ids = result.get("distracting_tab_ids", [])
        summary = result.get("summary_bullets", [])

        if not isinstance(distraction_ids, list):
            distraction_ids = []

        if not isinstance(summary, list):
            summary = []

        valid_ids = {tab["id"] for tab in clean_tabs}

        distraction_ids = [
            int(tab_id)
            for tab_id in distraction_ids
            if str(tab_id).isdigit()
            and int(tab_id) in valid_ids
        ]

        # Safety filter: never recommend closing local or TabMind pages.
        safe_tabs = {
            tab["id"]: tab
            for tab in clean_tabs
        }

        distraction_ids = [
            tab_id
            for tab_id in distraction_ids
            if not (
                "localhost" in safe_tabs[tab_id]["url"].lower()
                or "127.0.0.1" in safe_tabs[tab_id]["url"].lower()
                or "tabmind" in safe_tabs[tab_id]["url"].lower()
            )
        ]

        summary = [
            str(item)[:1000]
            for item in summary[:5]
            if isinstance(item, str) and item.strip()
        ]

        if len(summary) != 5:
            return jsonify({
                "error": "AI did not generate exactly five research insights."
            }), 502

        display_tabs = [
            {
                "id": tab["id"],
                "title": tab["title"],
                "url": tab["url"]
            }
            for tab in clean_tabs
        ]

        final_result = {
            "goal": goal,
            "tabs": display_tabs,
            "distracting_tab_ids": distraction_ids,
            "summary_bullets": summary
        }

        latest_analysis = final_result

        return jsonify(final_result)

    except urllib.error.URLError as error:

        print("Network error:", str(error))

        return jsonify({
            "error": "Unable to connect to Gemini. Check your internet connection."
        }), 502

    except (KeyError, IndexError, TypeError, ValueError) as error:

        print("Invalid Gemini response:", str(error))

        return jsonify({
            "error": "Gemini returned an unexpected response. Please try again."
        }), 502

    except Exception as error:

        print("Unexpected AI error:", str(error))

        return jsonify({
            "error": "AI analysis failed.",
            "details": str(error)
        }), 500


@app.route("/api/latest")
def get_latest_analysis():

    if latest_analysis is None:
        return jsonify({
            "message": "No analysis has been performed yet."
        })

    return jsonify(latest_analysis)


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True
    )
