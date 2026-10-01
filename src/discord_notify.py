import os
import requests


DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")


def send_leads_to_discord(leads: list[dict]) -> None:
    """Send the top leads to Discord using a webhook."""

    if not DISCORD_WEBHOOK_URL:
        raise RuntimeError(
            "DISCORD_WEBHOOK_URL is not configured"
        )

    if not leads:
        payload = {
            "content": "🔎 AI Client Finder\n\nNo new leads found in this run."
        }

        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=30,
        )

        response.raise_for_status()
        return

    header = {
        "content": (
            "🔎 **AI CLIENT FINDER**\n"
            f"Found **{len(leads[:5])} new potential leads**."
        )
    }

    response = requests.post(
        DISCORD_WEBHOOK_URL,
        json=header,
        timeout=30,
    )

    response.raise_for_status()

    for index, lead in enumerate(leads[:5], start=1):
        business_name = lead.get(
            "business_name",
            "Unknown Business"
        )

        category = lead.get(
            "category",
            "Unknown"
        )

        location = lead.get(
            "location",
            "Unknown"
        )

        phone = lead.get("phone") or "Not found"
        email = lead.get("email") or "Not found"

        website = (
            lead.get("website")
            or "Not found in retrieved sources"
        )

        status = lead.get(
            "website_status",
            "Unknown"
        )

        score = lead.get(
            "score",
            0
        )

        source = lead.get(
            "source_url",
            ""
        )

        evidence = (
            lead.get("evidence")
            or "No additional evidence."
        )

        # Keep Discord message readable.
        if len(evidence) > 400:
            evidence = evidence[:397] + "..."

        message = (
            f"**#{index} — {business_name}**\n\n"
            f"📂 **Category:** {category}\n"
            f"📍 **Location:** {location}\n"
            f"📞 **Phone:** {phone}\n"
            f"📧 **Email:** {email}\n"
            f"🌐 **Website:** {website}\n"
            f"🔍 **Website status:** {status}\n"
            f"⭐ **Score:** {score}/100\n"
            f"📝 **Evidence:** {evidence}\n"
            f"🔗 **Source:** {source}"
        )

        payload = {
            "content": message
        }

        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=30,
        )

        response.raise_for_status()
