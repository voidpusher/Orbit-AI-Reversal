from app.services.deep_analysis import (
    analyze_performance,
    analyze_privacy,
    analyze_security,
    analyze_seo,
)
from app.services.page_signals import extract_page_signals

HTML = """
<!doctype html><html lang="en"><head>
<title>Acme — Modern Issue Tracking for Teams</title>
<meta name="description" content="Acme helps engineering teams plan, track, and ship software faster with a keyboard-first workflow.">
<meta property="og:title" content="Acme"><meta property="og:description" content="Track work">
<meta property="og:image" content="/card.png"><meta name="twitter:card" content="summary_large_image">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="canonical" href="https://acme.com/"><link rel="preconnect" href="https://cdn.acme.com">
<link rel="alternate" hreflang="en" href="/en"><link rel="alternate" hreflang="de" href="/de">
<script type="application/ld+json">{"@type":"SoftwareApplication","name":"Acme"}</script>
<script src="https://js.stripe.com/v3"></script>
<script src="https://cdn.segment.com/analytics.js"></script>
<img src="/hero.webp" loading="lazy"><img src="/logo.svg">
</head><body><main><h1>Plan and build</h1><p>Lots of real server-rendered text content here to look like SSR output for the analyzer to classify as server rendered rather than an empty client shell.</p></main></body></html>
"""

HEADERS = {
    "content-security-policy": "default-src 'self'; script-src 'self'; frame-ancestors 'none'",
    "strict-transport-security": "max-age=63072000; includeSubDomains; preload",
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin-when-cross-origin",
    "content-encoding": "br",
    "cache-control": "public, max-age=31536000, immutable",
    "x-vercel-cache": "HIT",
    "x-vercel-id": "iad1::abc",
    "content-type": "text/html; charset=utf-8",
}


def _signals():
    return extract_page_signals(
        HTML, HEADERS, "https://acme.com/", "HTTP/2", 200,
        ["session=x; Secure; HttpOnly; SameSite=Lax", "ga=y"],
    )


def test_page_signals_extract_rich_detail() -> None:
    s = _signals()
    assert s["title"].startswith("Acme")
    assert s["lang"] == "en"
    assert "SoftwareApplication" in s["jsonld_types"]
    assert s["external_script_count"] == 2
    assert "js.stripe.com" in s["third_party_hosts"]
    assert s["image_formats"].get("webp") == 1 and s["image_formats"].get("svg") == 1
    assert s["security_headers"]["hsts"].startswith("max-age")
    assert sorted(s["hreflangs"]) == ["de", "en"]
    assert len(s["cookies"]) == 2


def test_security_grade_and_findings() -> None:
    section = analyze_security([_signals()])
    assert section["grade"] in {"A", "B"}
    titles = [f["title"] for f in section["findings"]]
    assert any("HSTS" in t for t in titles)
    # The weak second cookie (no Secure/SameSite) must be flagged.
    assert any("Cookie" in t for t in titles)


def test_performance_and_seo_are_specific() -> None:
    perf = analyze_performance([_signals()])
    assert any("HTTP/2" in f["title"] or "Modern transport" in f["title"] for f in perf["findings"])
    assert any(m["label"] == "Transport" and "2" in m["value"] for m in perf["metrics"])

    seo = analyze_seo([_signals()])
    assert seo["grade"] in {"A", "B"}
    assert any("Structured data" in f["title"] for f in seo["findings"])


def test_privacy_detects_trackers() -> None:
    section = analyze_privacy([_signals()])
    titles = " ".join(f["title"] for f in section["findings"])
    assert "tracker" in titles.lower() or "Third-party" in titles
