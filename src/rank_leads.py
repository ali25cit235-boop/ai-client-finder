def rank_lead(lead: dict) -> dict:
    """Score a lead based on useful, verifiable signals."""

    score = 0
    reasons = []

    website_status = lead.get("website_status", "")

    if website_status == "not_found_in_sources":
        score += 45
        reasons.append("No official website found in retrieved sources")

    elif website_status == "unreachable_or_blocked":
        score += 20
        reasons.append("Candidate website could not be reached")

    if lead.get("phone"):
        score += 15
        reasons.append("Public phone number available")

    if lead.get("email"):
        score += 15
        reasons.append("Public business email available")

    if lead.get("category"):
        score += 10
        reasons.append("Business category identified")

    if lead.get("location"):
        score += 5
        reasons.append("Business location identified")

    if lead.get("source_url"):
        score += 10
        reasons.append("Source page available")

    return {
        **lead,
        "score": min(score, 100),
        "score_reasons": reasons,
    }


def rank_leads(leads: list[dict]) -> list[dict]:
    ranked = [rank_lead(lead) for lead in leads]

    return sorted(
        ranked,
        key=lambda lead: (
            lead.get("score", 0),
            bool(lead.get("phone")),
            bool(lead.get("email")),
        ),
        reverse=True,
    )
