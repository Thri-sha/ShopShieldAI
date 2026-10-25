from urllib.parse import urlparse
import ipaddress
import re

SUSPICIOUS_TERMS = (
    "login", "verify", "wallet", "bonus", "free-gift", "gift",
    "urgent", "secure-update", "account-check", "claim-prize"
)

def analyze_website(url):
    """A transparent URL-pattern heuristic, not a verified AI or blacklist scan."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    reasons = []
    score = 100

    if parsed.scheme != "https":
        score -= 20
        reasons.append("The URL does not use HTTPS.")
    else:
        reasons.append("The URL uses HTTPS, which encrypts the connection but does not prove the shop is genuine.")

    if len(url) > 100:
        score -= 10
        reasons.append("The URL is unusually long.")
    if host.count("-") >= 2:
        score -= 10
        reasons.append("The domain contains several hyphens.")
    if sum(ch.isdigit() for ch in host) >= 4:
        score -= 10
        reasons.append("The domain contains many digits.")

    try:
        ipaddress.ip_address(host)
        score -= 30
        reasons.append("The address uses an IP number instead of a typical domain name.")
    except ValueError:
        pass

    matched = [term for term in SUSPICIOUS_TERMS if term in url.lower()]
    if matched:
        score -= min(25, 8 * len(matched))
        reasons.append("The URL contains potentially misleading words: " + ", ".join(matched) + ".")

    if "@" in url:
        score -= 20
        reasons.append("The URL contains an @ symbol, which can be used to disguise the destination.")

    score = max(0, min(100, score))
    if score >= 75:
        label, color = "LOW URL RISK", "safe"
        summary = "No major warning patterns were detected by this basic URL check."
    elif score >= 45:
        label, color = "CAUTION", "warning"
        summary = "Some URL patterns deserve extra checking before you buy."
    else:
        label, color = "HIGH URL RISK", "danger"
        summary = "Several warning patterns were detected. Avoid entering payment details until you verify the shop."

    reasons.append("This is a rule-based estimate. It does not contact the website, check a live blacklist, verify business registration, or guarantee safety.")
    return {"score": score, "label": label, "color": color, "summary": summary, "reasons": reasons}
