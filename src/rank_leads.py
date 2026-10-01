def rank_lead(lead: dict) -> dict:
    """Score a lead using available, verifiable business information."""
    score = 0
    reasons = []

    if not lead.get("website"):
        score += 40
        reasons.append("No website URL found in the available sources")

    if lead.get("phone"):
        score += 15
        reasons.append("Public phone number available")

    if lead.get("email"):
        score += 15
        reasons.append("Public business email available")

    if lead.get("business_name"):
        score += 10

    if lead.get("source_url"):
        score += 10
        reasons.append("Source link available for review")

    if lead.get("category"):
        score += 10
        reasons.append("Business category identified")

    return {
        **lead,
        "score": min(score, 100),
        "score_reasons": reasons,
    }


def rank_leads(leads: list[dict]) -> list[dict]:
    """Return leads sorted by score, highest first."""
    ranked = [rank_lead(lead) for lead in leads]
    return sorted(
        ranked,
        key=lambda lead: lead["score"],
        reverse=True,
    )
