from datetime import datetime, timezone


def create_report(leads: list[dict]) -> str:
    lines = [
        "# AI Client Finder — Lead Report",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Leads found: {len(leads)}",
        "",
        "> Website status is based on retrieved public sources. "
        "A missing website in those sources is not absolute proof that "
        "the business has no website.",
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
            f"- Phone: {lead.get('phone') or 'Not found'}",
            f"- Public email: {lead.get('email') or 'Not found'}",
            f"- Official website: {lead.get('website') or 'Not found in retrieved sources'}",
            f"- Website status: {lead.get('website_status', 'Unknown')}",
            f"- Score: {lead.get('score', 0)}/100",
            f"- Evidence: {lead.get('evidence', 'Not provided')}",
            f"- Source: {lead.get('source_url', 'Not provided')}",
            "",
        ])

    return "\n".join(lines) + "\n"
