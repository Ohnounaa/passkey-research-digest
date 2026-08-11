import os
import feedparser
import resend

# Expanded list of target subreddits for Passkey, E-commerce, and Fintech UX tracking
TARGET_SUBREDDITS = [
    "Passkeys",
    "passkey",
    "Yubikey",
    "Cybersecurity",
    "Fintech",
    "Ecommerce",
    "WebAuthn",
    "Shopify",
    "webdev",
    "1Password",
    "Bitwarden", “Chase”,
    “CapitalOne”,
     “WellsFargoBank”,
“DigitalPrivacy”,
“BankOfAmerica”,
“USAA”,
“Schwab”,
]

DOMAIN_KEYWORDS = [
    "passkey",
    "passkeys",
    "webauthn",
    "fido2",
    "checkout",
    "bank",
    "banking",
    "ux",
    "friction",
    "recovery",
    "conversion",
]


def fetch_reddit_posts():
    findings = []
    for sub in TARGET_SUBREDDITS:
        rss_url = f"https://www.reddit.com/r/{sub}/search.rss?q=passkey&sort=new&t=day"
        feed = feedparser.parse(rss_url)

        for entry in feed.entries:
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            combined_text = f"{title} {summary}".lower()

            if any(term in combined_text for term in DOMAIN_KEYWORDS):
                findings.append(
                    {
                        "title": title,
                        "link": entry.get("link", "#"),
                        "subreddit": sub,
                        "updated": entry.get("updated", "Today"),
                    }
                )
    return findings


def send_digest():
    findings = fetch_reddit_posts()

    if not findings:
        html_body = "<p>No new passkey discussions found today in tracked subreddits.</p>"
    else:
        html_body = "<h2>Daily Passkey Market Research Digest</h2><hr/><br/>"
        for item in findings:
            html_body += f"""
            <div style="margin-bottom: 16px; padding: 12px; border-left: 4px solid #0070f3; background-color: #f9f9f9;">
                <h3 style="margin: 0 0 6px 0;"><a href="{item['link']}">{item['title']}</a></h3>
                <span style="font-size: 12px; color: #666;">r/{item['subreddit']} • {item['updated']}</span>
            </div>
            """

    resend.api_key = os.environ["RESEND_API_KEY"]
    resend.Emails.send(
        {
            "from": "onboarding@resend.dev",
            "to": os.environ["RECIPIENT_EMAIL"],
            "subject": f"Passkey Digest: {len(findings)} New Reddit Threads",
            "html": html_body,
        }
    )


if __name__ == "__main__":
    send_digest()
