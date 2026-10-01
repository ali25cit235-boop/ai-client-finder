from datetime import datetime, timezone


def create_report(leads: list[dict]) -> str:
    """Create a readable Markdown report for the selected leads."""
    lines = [
        "# AI Client Finder — Lead Report",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Leads found: {len(leads)}",
        "",
    ]

    if not leads:
        lines.append("No new leads found in this run.")
        return "\n".join(lines) + "\n"

    for index, lead in enumerate(leads[:5], start=1):
        lines.extend([
            f"## {index}. {lead.get('business_name', 'Unknown business')}",
            f"- Category: {lead.get('category', 'Unknown')}",
            f"- Location: {lead.get('location', 'Unknown')}",
            f"- Phone: {lead.get('phone', 'Not found')}",
            f"- Public email: {lead.get('email', 'Not found')}",
            f"- Website URL: {lead.get('website') or 'Not found — needs verification'}",
            f"- Website check: {lead.get('website_status', 'Not checked')}",
            f"- Score: {lead.get('score', 0)}/100",
            f"- Source: {lead.get('source_url', 'Not provided')}",
            "",
        ])

    return "\n".join(lines) + "\n"
