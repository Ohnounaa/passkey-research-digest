import os
import json
import requests
import resend
from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# 1. FETCH REDDIT DATA VIA PUBLIC JSON ENDPOINTS (POSTS + COMMENTS)
# ---------------------------------------------------------------------------
SEARCH_QUERIES = [
    "Chase passkey",
    "Chase passkeys",
    "bank passkey",
    "banking passkey",
    "Capital One passkey",
    "Wells Fargo passkey",
    "passkey checkout",
    "passkey UX",
]

SUBREDDITS = [
    "Passkeys",
    "passkey",
    "Yubikey",
    "Cybersecurity",
    "Fintech",
    "Ecommerce",
    "WebAuthn",
    "Shopify",
    "1Password",
    "Bitwarden",
    "banking",
    "Chase",
    "CapitalOne",
    "WellsFargoBank",
    "DigitalPrivacy",     
    “BankOfAmerica",
    “USAA",
    “Schwab”,
    “cybersecurity”,
]

HEADERS = {"User-Agent": "PasskeyExecutiveDigest/2.0"}

def fetch_raw_reddit_data():
    raw_threads = []
    seen_ids = set()

    for query in SEARCH_QUERIES:
        url = f"https://www.reddit.com/search.json?q={query}&sort=new&t=month&limit=25"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                continue
            data = resp.json()
            for post in data.get("data", {}).get("children", []):
                pdata = post["data"]
                pid = pdata["id"]
                if pid in seen_ids:
                    continue
                seen_ids.add(pid)

                # Fetch top comments for comment-level matching
                comments = []
                comments_url = f"https://www.reddit.com{pdata['permalink']}.json?limit=10"
                c_resp = requests.get(comments_url, headers=HEADERS, timeout=5)
                if c_resp.status_code == 200:
                    try:
                        c_data = c_resp.json()
                        if len(c_data) > 1:
                            for c in c_data[1]["data"]["children"]:
                                cbody = c.get("data", {}).get("body")
                                if cbody:
                                    comments.append(cbody[:300])
                    except Exception:
                        pass

                raw_threads.append({
                    "id": pid,
                    "title": pdata.get("title", ""),
                    "subreddit": pdata.get("subreddit", ""),
                    "url": f"https://reddit.com{pdata.get('permalink', '')}",
                    "created_utc": pdata.get("created_utc", 0),
                    "score": pdata.get("score", 0),
                    "upvote_ratio": pdata.get("upvote_ratio", 0),
                    "num_comments": pdata.get("num_comments", 0),
                    "selftext": (pdata.get("selftext", "") or "")[:500],
                    "top_comments": comments
                })
        except Exception as e:
            print(f"Error fetching search query '{query}': {e}")

    return raw_threads

# ---------------------------------------------------------------------------
# 2. SYNTHESIZE REPORT VIA GEMINI API
# ---------------------------------------------------------------------------
SYSTEM_INSTRUCTION = """
You are a senior market research analyst specializing in authentication, passkeys, and fintech/banking UX.
Your job is to analyze raw Reddit threads and produce a highly structured JSON report following these exact rules:

1. Executive Snapshot (5-8 lines total):
   - What materially changed in "Chase" "passkeys" in the last 24h.
   - Any notable issues/rumors vs. confirmed user experiences regarding Chase and banks.
   - One line on broader passkey/cyber trends if relevant.

2. Top 10 Items (Ranked):
   - Select up to 10 most relevant items. Target allocation: ~6 Chase+passkeys, ~3 other banks+passkeys, ~1 general passkey/cyber.
   - For each item, indicate:
     - title
     - subreddit
     - post_age (e.g. "5 hours ago" or "12 days ago")
     - engagement (string formatted like: "Score: 45 | Upvote Ratio: 88% | Comments: 12")
     - matched_via ("post text" or "comment text")
     - url
     - why_it_matters (1 concise sentence on fintech or financial services angle)
     - tags (array of strings, e.g. ["Availability/Rollout", "iOS", "Lockout/Recovery", "Fraud/Account Takeover", "Phishing Resistance"])

3. Themes (Top 3-6):
   - Recurring themes across the threads.
   - Each theme needs:
     - theme_name
     - count (integer count of contributing posts/comments)
     - evidence (array of 1-2 objects containing "quote_snippet" and "url")

4. Catch-up Section:
   - Identify older threads (older than 2 days up to 14 days) that have recent commentary or relevance.
   - Include array of objects with "title", "url", "subreddit", and "reason_revived".

Return ONLY valid JSON matching this schema.
"""

def generate_report_json(threads):
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    
    prompt = f"Analyze these raw Reddit threads/comments and return the structured report JSON:\n\n{json.dumps(threads[:35])}"

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    return json.loads(response.text)

# ---------------------------------------------------------------------------
# 3. BUILD EXECUTIVE HTML EMAIL & DISPATCH VIA RESEND
# ---------------------------------------------------------------------------
def build_html_report(report):
    # Executive Snapshot
    snapshot_lines = report.get("executive_snapshot", [])
    snapshot_html = "".join([f"<li style='margin-bottom: 6px;'>{line}</li>" for line in snapshot_lines])

    # Top 10 Table
    table_rows = ""
    for item in report.get("top_items", []):
        tags_str = " ".join([f"<span style='background:#e2e8f0; color:#1e293b; padding:2px 6px; border-radius:4px; font-size:11px; font-weight:600;'>{t}</span>" for t in item.get("tags", [])])
        table_rows += f"""
        <tr style="border-bottom: 1px solid #e2e8f0;">
            <td style="padding: 10px; font-size: 13px;">
                <a href="{item.get('url')}" style="color: #0284c7; font-weight: bold; text-decoration: none;">{item.get('title')}</a><br/>
                <span style="font-size: 11px; color: #64748b;">r/{item.get('subreddit')} • {item.get('post_age')} • Matched via <b>{item.get('matched_via')}</b></span>
            </td>
            <td style="padding: 10px; font-size: 11px; color: #475569; white-space: nowrap;">{item.get('engagement')}</td>
            <td style="padding: 10px; font-size: 12px; color: #334155;">{item.get('why_it_matters')}</td>
            <td style="padding: 10px;">{tags_str}</td>
        </tr>
        """

    # Themes
    themes_html = ""
    for theme in report.get("themes", []):
        evidence_list = "".join([f"<li><i>\"{ev.get('quote_snippet')}\"</i> — <a href='{ev.get('url')}'>Link</a></li>" for ev in theme.get("evidence", [])])
        themes_html += f"""
        <div style="margin-bottom: 14px; padding: 12px; background: #f8fafc; border-left: 4px solid #0284c7; border-radius: 4px;">
            <strong style="font-size: 14px; color: #0f172a;">{theme.get('theme_name')}</strong> 
            <span style="font-size: 12px; color: #64748b;">({theme.get('count')} references)</span>
            <ul style="margin: 6px 0 0 0; padding-left: 20px; font-size: 12px; color: #334155;">
                {evidence_list}
            </ul>
        </div>
        """

    # Catch-Up
    catchup_items = report.get("catch_up_section", [])
    catchup_html = ""
    if catchup_items:
        catchup_html = "<h3>4. Catch-Up Section (Revived Conversations)</h3><ul>"
        for c in catchup_items:
            catchup_html += f"<li><a href='{c.get('url')}'><b>{c.get('title')}</b></a> (r/{c.get('subreddit')}) — {c.get('reason_revived')}</li>"
        catchup_html += "</ul>"

    # Full Email HTML Shell
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #0f172a; line-height: 1.5; max-width: 900px; margin: 0 auto; padding: 20px;">
        <h1 style="border-bottom: 2px solid #0284c7; padding-bottom: 8px; color: #0369a1; font-size: 22px;">Daily Passkey Market Research Digest: Chase & Banking</h1>
        
        <!-- SECTION 1 -->
        <div style="background: #f0f9ff; border: 1px solid #bae6fd; padding: 16px; border-radius: 6px; margin-bottom: 24px;">
            <h2 style="margin-top: 0; font-size: 16px; color: #0369a1;">1. Executive Snapshot</h2>
            <ul style="margin: 0; padding-left: 20px; font-size: 13px; color: #1e293b;">
                {snapshot_html}
            </ul>
        </div>

        <!-- SECTION 2 -->
        <h2 style="font-size: 16px; color: #0f172a; margin-bottom: 12px;">2. Top Ranked Items</h2>
        <table style="width: 100%; border-collapse: collapse; text-align: left; margin-bottom: 24px;">
            <thead>
                <tr style="background: #f1f5f9; border-bottom: 2px solid #cbd5e1; font-size: 12px; color: #475569;">
                    <th style="padding: 8px;">Thread / Subreddit</th>
                    <th style="padding: 8px;">Engagement</th>
                    <th style="padding: 8px;">Why It Matters</th>
                    <th style="padding: 8px;">Tags</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>

        <!-- SECTION 3 -->
        <h2 style="font-size: 16px; color: #0f172a; margin-bottom: 12px;">3. Recurring Themes</h2>
        {themes_html}

        <!-- SECTION 4 -->
        {catchup_html}
    </body>
    </html>
    """
    return full_html

def send_email():
    raw_threads = fetch_raw_reddit_data()
    if not raw_threads:
        print("No threads fetched.")
        return

    report_json = generate_report_json(raw_threads)
    html_content = build_html_report(report_json)

    resend.api_key = os.environ["RESEND_API_KEY"]
    resend.Emails.send({
        "from": "onboarding@resend.dev",
        "to": os.environ["RECIPIENT_EMAIL"],
        "subject": "Daily Passkey Research: Executive Chase & Banking Report",
        "html": html_content,
    })
    print("Report sent successfully!")

if __name__ == "__main__":
    send_email()
