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

    # Validate user input
    if not goal:
        return jsonify({
            "error": "Please enter your research goal."
        }), 400

    if not isinstance(tabs, list) or not tabs:
        return jsonify({
            "error": "No browser tabs were received."
        }), 400

    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        return jsonify({
            "error": "Gemini API key is not configured."
        }), 500

    # Clean and validate browser tabs
    clean_tabs = []

    for tab in tabs[:MAX_TABS]:

        try:
            tab_id = int(tab["id"])

            if tab_id <= 0:
                continue

            clean_tabs.append({
                "id": tab_id,
                "title": str(
                    tab.get("title", "Untitled")
                )[:200],
                "url": str(
                    tab.get("url", "")
                )[:500],
                "content": str(
                    tab.get("content", "")
                )[:MAX_CONTENT_LENGTH]
            })

        except (KeyError, TypeError, ValueError):
            continue

    if not clean_tabs:
        return jsonify({
            "error": "No valid browser tabs were received."
        }), 400

    # Prepare AI instructions
    prompt = f"""
You are TabMind, an advanced AI browser research
and productivity assistant.

USER'S RESEARCH GOAL:
{goal}

BROWSER TABS AND EXTRACTED WEBPAGE CONTENT:
{json.dumps(clean_tabs, ensure_ascii=False)}

YOUR RESPONSIBILITIES:

1. Understand the user's research goal.
2. Analyse the actual extracted webpage content.
3. Identify webpages relevant to the user's goal.
4. Identify unrelated and distracting webpages.
5. Return distracting tab IDs using their original IDs.
6. Identify important facts, concepts and information.
7. Generate exactly FIVE useful research insights.
8. Identify knowledge gaps and suggest useful
   research directions within the five insights.
9. Avoid repeating the same information.
10. Never invent facts or claim to have visited
    webpages that were not provided.
11. If content is unavailable, cautiously use
    the webpage title and URL.

IMPORTANT:
- Only return IDs belonging to the provided tabs.
- Do not recommend closing relevant research tabs.
- Be accurate and useful.
- Return exactly five concise insights.

RETURN VALID JSON ONLY:

{{
    "distracting_tab_ids": [],
    "summary_bullets": [
        "Research insight 1",
        "Research insight 2",
        "Research insight 3",
        "Research insight 4",
        "Research insight 5"
    ]
}}
"""

    # Gemini API request
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

        # Retry temporary server overloads
        for attempt in range(4):

            try:

                with urllib.request.urlopen(
                    req,
                    timeout=90
                ) as response:

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

                # Retry temporary server errors
                if error.code == 503 and attempt < 3:

                    wait_time = 2 ** (attempt + 1)

                    print(
                        f"Gemini busy. Retrying in "
                        f"{wait_time} seconds..."
                    )

                    time.sleep(wait_time)
                    continue

                if error.code == 429:

                    return jsonify({
                        "error": (
                            "Gemini API request limit reached. "
                            "Please wait before trying again."
                        ),
                        "details": error_details
                    }), 429

                if error.code == 503:

                    return jsonify({
                        "error": (
                            "Gemini is temporarily overloaded. "
                            "Please try again later."
                        ),
                        "details": error_details
                    }), 503

                return jsonify({
                    "error": "Gemini API request failed.",
                    "details": error_details
                }), 502

        if api_response is None:

            return jsonify({
                "error": "Gemini did not return a response."
            }), 502

        # Extract AI response
        result_text = (
            api_response["candidates"][0]
            ["content"]["parts"][0]["text"]
        )

        result = json.loads(result_text)

        # Validate AI response
        distraction_ids = result.get(
            "distracting_tab_ids", []
        )

        summary = result.get(
            "summary_bullets", []
        )

        if not isinstance(distraction_ids, list):
            distraction_ids = []

        if not isinstance(summary, list):
            summary = []

        valid_ids = {
            tab["id"] for tab in clean_tabs
        }

        distraction_ids = [
            int(tab_id)
            for tab_id in distraction_ids
            if str(tab_id).isdigit()
            and int(tab_id) in valid_ids
        ]

        summary = [
            str(item)[:1000]
            for item in summary[:5]
            if isinstance(item, str) and item.strip()
        ]

        if len(summary) != 5:

            return jsonify({
                "error": (
                    "AI did not generate exactly five "
                    "research insights. Please try again."
                )
            }), 502

        # Remove webpage text before returning or storing
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
            "error": (
                "Unable to connect to Gemini. "
                "Check your internet connection."
            )
        }), 502

    except (KeyError, IndexError, TypeError, ValueError) as error:

        print("Invalid Gemini response:", str(error))

        return jsonify({
            "error": (
                "Gemini returned an unexpected response. "
                "Please try again."
            )
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