"""Turn rich page signals into specific, graded, evidence-cited findings.

Each analyzer returns a section with a human summary, a confidence, an optional
letter grade, quantified metrics, and a list of findings. Findings carry a
status (good / warn / bad / info) and the concrete evidence that produced them —
never a generic claim.
"""

from __future__ import annotations

import re

# IATA / provider region codes → human-readable locations.
_REGION_CODES = {
    "iad": "Washington, D.C. (US East)", "dca": "Washington, D.C. (US East)", "cle": "Cleveland (US East)",
    "sfo": "San Francisco (US West)", "sjc": "San Jose (US West)", "pdx": "Portland (US West)",
    "dfw": "Dallas (US Central)", "ord": "Chicago (US Central)", "atl": "Atlanta (US East)",
    "lhr": "London (EU)", "cdg": "Paris (EU)", "fra": "Frankfurt (EU)", "arn": "Stockholm (EU)",
    "dub": "Dublin (EU)", "ams": "Amsterdam (EU)", "hnd": "Tokyo (Asia)", "nrt": "Tokyo (Asia)",
    "sin": "Singapore (Asia)", "hkg": "Hong Kong (Asia)", "icn": "Seoul (Asia)", "bom": "Mumbai (Asia)",
    "syd": "Sydney (Oceania)", "gru": "São Paulo (South America)",
}


def _finding(title: str, detail: str, status: str, evidence: str = "") -> dict:
    return {"title": title, "detail": detail, "status": status, "evidence": evidence}


def _grade(score: int) -> str:
    return "A" if score >= 90 else "B" if score >= 78 else "C" if score >= 65 else "D" if score >= 50 else "F"


def _region(code: str | None) -> str | None:
    if not code:
        return None
    tokens = re.findall(r"[A-Za-z]{3}", code)
    for token in tokens:
        if token.lower() in _REGION_CODES:
            return _REGION_CODES[token.lower()]
    return None


def _primary(pages: list[dict]) -> dict:
    return pages[0] if pages else {}


# ---------------------------------------------------------------------------
# Security posture
# ---------------------------------------------------------------------------
def _fmt_bytes(n: int) -> str:
    if n >= 1_048_576:
        return f"{n / 1_048_576:.1f} MB"
    if n >= 1024:
        return f"{round(n / 1024)} KB"
    return f"{n} B"


def analyze_security(pages: list[dict], probes: dict | None = None) -> dict:
    page = _primary(pages)
    sec = page.get("security_headers", {})
    findings: list[dict] = []
    score = 40  # baseline for serving over HTTPS
    probes = probes or {}

    csp = sec.get("csp")
    if csp:
        unsafe = "'unsafe-inline'" in csp or "unsafe-inline" in csp
        has_frame_ancestors = "frame-ancestors" in csp
        directives = len([d for d in csp.split(";") if d.strip()])
        if unsafe:
            findings.append(_finding("CSP allows 'unsafe-inline'", f"A Content-Security-Policy is set ({directives} directives) but permits inline scripts/styles, weakening its XSS protection.", "warn", csp[:120]))
            score += 12
        else:
            findings.append(_finding("Strong Content-Security-Policy", f"A CSP with {directives} directives restricts resource origins without 'unsafe-inline'.", "good", csp[:120]))
            score += 22
        if has_frame_ancestors:
            score += 3
    else:
        findings.append(_finding("No Content-Security-Policy", "No CSP header was returned, so the app relies on browser defaults against injection.", "bad", "content-security-policy: (absent)"))

    hsts = sec.get("hsts")
    if hsts:
        max_age = re.search(r"max-age=(\d+)", hsts)
        years = int(max_age.group(1)) / 31_536_000 if max_age else 0
        preload = "preload" in hsts
        subdomains = "includesubdomains" in hsts.lower()
        detail = f"HSTS enforces HTTPS for ~{years:.1f} year(s)" + (", includes subdomains" if subdomains else "") + (", preloaded" if preload else "")
        findings.append(_finding("HSTS enabled", detail + ".", "good", hsts[:100]))
        score += 12 + (3 if preload else 0)
    else:
        findings.append(_finding("No HSTS header", "Strict-Transport-Security is absent; first visits may be downgraded to HTTP.", "warn", "strict-transport-security: (absent)"))

    if sec.get("x_content_type_options"):
        findings.append(_finding("MIME sniffing blocked", "X-Content-Type-Options: nosniff is set.", "good", f"x-content-type-options: {sec['x_content_type_options']}"))
        score += 6
    if sec.get("x_frame_options") or (csp and "frame-ancestors" in csp):
        findings.append(_finding("Clickjacking protection", "Framing is restricted via X-Frame-Options or CSP frame-ancestors.", "good", f"x-frame-options: {sec.get('x_frame_options', 'via CSP')}"))
        score += 6
    else:
        findings.append(_finding("No framing protection", "Neither X-Frame-Options nor CSP frame-ancestors was found — clickjacking is possible.", "warn", "x-frame-options: (absent)"))
    if sec.get("referrer_policy"):
        findings.append(_finding("Referrer-Policy set", f"Referrer leakage is controlled ({sec['referrer_policy']}).", "good", f"referrer-policy: {sec['referrer_policy']}"))
        score += 4
    if sec.get("permissions_policy"):
        findings.append(_finding("Permissions-Policy set", "Powerful browser features are explicitly gated.", "good", "permissions-policy: present"))
        score += 4
    if sec.get("coop") or sec.get("coep"):
        findings.append(_finding("Cross-origin isolation", "COOP/COEP headers harden the browsing context.", "good", "cross-origin-*-policy: present"))
        score += 4

    # Cookie hygiene across all pages.
    all_cookies = [c for p in pages for c in p.get("cookies", [])]
    weak = [c for c in all_cookies if not c["secure"] or c["same_site"] is None]
    if all_cookies:
        if weak:
            findings.append(_finding("Cookie flags need hardening", f"{len(weak)} of {len(all_cookies)} observed cookie(s) lack Secure or SameSite.", "warn", ", ".join(c["name"] for c in weak[:4])))
        else:
            findings.append(_finding("Cookies hardened", f"All {len(all_cookies)} observed cookies use Secure + SameSite.", "good", ", ".join(c["name"] for c in all_cookies[:4])))
            score += 4

    # TLS / certificate intelligence from the host-level probe.
    tls = probes.get("tls", {})
    metrics = [
        {"label": "Security headers", "value": f"{sum(1 for v in sec.values() if v)}/8"},
        {"label": "Cookies seen", "value": str(len(all_cookies))},
    ]
    if tls.get("available"):
        proto = tls.get("protocol", "TLS")
        modern_tls = "1.3" in (proto or "") or "1.2" in (proto or "")
        expiry = tls.get("days_until_expiry")
        detail = (
            f"{proto} via {tls.get('cipher', 'a modern cipher')}; certificate issued by "
            f"{tls.get('issuer', 'a CA')}"
            + (f", wildcard covering {tls.get('san_count', 0)} names" if tls.get("wildcard") else f", {tls.get('san_count', 0)} SAN(s)")
            + (f", expires in {expiry} days" if expiry is not None else "")
            + "."
        )
        status = "good" if modern_tls and (expiry is None or expiry > 14) else "warn"
        findings.append(_finding(f"TLS certificate ({tls.get('issuer', 'CA')})", detail, status,
                                 f"{proto}, {tls.get('cipher_bits', '?')}-bit, valid until {tls.get('valid_until', '')[:10]}"))
        score += 8 if modern_tls else 2
        if expiry is not None and expiry < 21:
            findings.append(_finding("Certificate expiring soon", f"The TLS certificate expires in {expiry} day(s).", "warn", f"valid_until {tls.get('valid_until', '')[:10]}"))
        metrics.append({"label": "TLS", "value": (proto or "TLS").replace("TLSv", "TLS ")})
        metrics.append({"label": "Cert expires", "value": f"{expiry}d" if expiry is not None else "—"})

    score = min(100, score)
    return {
        "summary": f"Observed HTTP + TLS security posture graded {_grade(score)} from headers, certificate, and cookies.",
        "confidence": 91,
        "grade": _grade(score),
        "score": score,
        "findings": findings,
        "metrics": metrics,
    }


# ---------------------------------------------------------------------------
# Performance & delivery
# ---------------------------------------------------------------------------
def analyze_performance(pages: list[dict], probes: dict | None = None) -> dict:
    page = _primary(pages)
    delivery = page.get("delivery", {})
    findings: list[dict] = []
    score = 55
    probes = probes or {}

    http_v = delivery.get("http_version") or "HTTP/1.1"
    if "2" in http_v or "3" in http_v:
        findings.append(_finding(f"Modern transport ({http_v})", "Multiplexed HTTP reduces connection overhead.", "good", http_v))
        score += 12
    else:
        findings.append(_finding("Legacy HTTP/1.1", "No HTTP/2 or HTTP/3 was negotiated on the initial response.", "warn", http_v))

    enc = delivery.get("content_encoding")
    if enc and ("br" in enc or "gzip" in enc or "zstd" in enc):
        findings.append(_finding(f"Text compression ({enc})", "Responses are compressed on the wire.", "good", f"content-encoding: {enc}"))
        score += 10
    else:
        findings.append(_finding("No text compression", "The document response was not compressed (no br/gzip).", "warn", f"content-encoding: {enc or '(absent)'}"))

    cache = delivery.get("cache_control") or ""
    cdn = delivery.get("cdn_cache_status")
    if "immutable" in cache or re.search(r"max-age=(\d{6,})", cache):
        findings.append(_finding("Aggressive static caching", "Long-lived / immutable cache directives keep assets at the edge.", "good", f"cache-control: {cache[:80]}"))
        score += 10
    if cdn:
        hit = "hit" in cdn.lower()
        findings.append(_finding(f"CDN cache {'HIT' if hit else cdn}", "The response was served from an edge cache." if hit else "Edge cache present but this response was not a hit.", "good" if hit else "info", f"cdn-cache: {cdn}"))
        score += 8 if hit else 3

    hints = page.get("resource_hints", {})
    hints_str = ", ".join(f"{k} ×{v}" for k, v in hints.items())
    if hints:
        findings.append(_finding("Uses resource hints", f"Preloads/preconnects speed up critical resources ({hints_str}).", "good", hints_str))
        score += 6
    else:
        findings.append(_finding("No resource hints", "No preload/preconnect/prefetch hints were found in the document head.", "info", ""))

    ext_scripts = page.get("external_script_count", 0)
    if ext_scripts > 25:
        findings.append(_finding("Heavy script fan-out", f"The page requests {ext_scripts} external scripts, which can delay interactivity.", "warn", f"{ext_scripts} <script src>"))
    elif ext_scripts:
        findings.append(_finding("Lean script graph", f"{ext_scripts} external scripts, {page.get('module_scripts', 0)} as ES modules.", "good", f"{ext_scripts} scripts"))
        score += 4

    fmts = page.get("image_formats", {})
    fmts_str = ", ".join(f"{k}: {v}" for k, v in fmts.items())
    modern = fmts.get("webp", 0) + fmts.get("avif", 0)
    if modern:
        findings.append(_finding("Modern image formats", f"{modern} image(s) use WebP/AVIF; {page.get('lazy_images', 0)} lazy-loaded.", "good", fmts_str))
        score += 5
    elif page.get("image_count", 0) > 3:
        findings.append(_finding("No next-gen images", f"{page.get('image_count')} images observed, none in WebP/AVIF.", "warn", fmts_str))

    # Real JavaScript transfer weight + source-map exposure from the bundle probe.
    bundles = probes.get("bundles", {})
    metrics = [
        {"label": "HTML weight", "value": f"{round(page.get('html_bytes', 0) / 1024)} KB"},
        {"label": "External scripts", "value": str(ext_scripts)},
        {"label": "Stylesheets", "value": str(page.get("stylesheet_count", 0))},
        {"label": "Transport", "value": http_v},
    ]
    if bundles.get("available") and bundles.get("total_bytes"):
        total = bundles["total_bytes"]
        largest = bundles.get("largest_bytes", 0)
        heavy = total > 1_048_576
        findings.append(_finding(
            "JavaScript payload measured",
            f"Orbit sized {bundles.get('analyzed', 0)} bundle(s): ~{_fmt_bytes(total)} of JavaScript shipped, largest ~{_fmt_bytes(largest)}."
            + (" That's a heavy client bundle that can delay time-to-interactive." if heavy else ""),
            "warn" if heavy else "good",
            (bundles.get("largest_url") or "").split("/")[-1][:60],
        ))
        score += 0 if heavy else 6
        metrics.append({"label": "JS shipped", "value": _fmt_bytes(total)})
        if bundles.get("sourcemaps_exposed"):
            findings.append(_finding(
                "Source maps publicly exposed",
                f"{bundles['sourcemaps_exposed']} bundle(s) serve a reachable .map file, exposing original (often TypeScript) source to anyone.",
                "bad",
                f"{bundles['sourcemaps_exposed']} .map file(s) returned HTTP 200",
            ))

    score = min(100, score)
    return {
        "summary": f"Delivery and front-end performance graded {_grade(score)} from transport, caching, bundle weight, and assets.",
        "confidence": 83,
        "grade": _grade(score),
        "score": score,
        "findings": findings,
        "metrics": metrics,
    }


# ---------------------------------------------------------------------------
# Rendering strategy & deployment fingerprint
# ---------------------------------------------------------------------------
def analyze_rendering(pages: list[dict]) -> dict:
    page = _primary(pages)
    delivery = page.get("delivery", {})
    nd = page.get("next_data")
    findings: list[dict] = []

    if page.get("has_ssr_content"):
        findings.append(_finding("Server-rendered HTML", f"The initial response already contains ~{page.get('text_bytes', 0)} bytes of text (SSR/SSG), aiding first paint and SEO.", "good", f"text ratio {page.get('text_ratio')}"))
    else:
        findings.append(_finding("Client-rendered shell", "The initial HTML is a near-empty shell; content is hydrated client-side (SPA), which can hurt SEO and first paint.", "warn", f"text bytes {page.get('text_bytes', 0)}"))

    strategy = "Client-side rendered (SPA)"
    if nd and nd.get("present"):
        strategy = "Next.js SSR/SSG"
        parts = []
        if nd.get("build_id"):
            parts.append(f"build {str(nd['build_id'])[:10]}")
        if nd.get("has_page_props"):
            parts.append("server page props hydrated")
        findings.append(_finding("Next.js data pipeline", "Serialized __NEXT_DATA__ exposes the build and page props: " + (", ".join(parts) or "present") + ".", "info", f"__NEXT_DATA__ {nd.get('props_bytes', 0)} bytes"))
        cdn = (delivery.get("cdn_cache_status") or "").lower()
        if "hit" in cdn or "stale" in cdn or "prerender" in cdn:
            findings.append(_finding("Incremental Static Regeneration likely", "An edge cache HIT/STALE on a Next.js page indicates ISR — pages are pre-rendered and revalidated on an interval.", "info", f"cache: {delivery.get('cdn_cache_status')}"))
    elif page.get("has_ssr_content"):
        strategy = "Server-side rendered"

    region = _region(delivery.get("region_hint"))
    if region:
        findings.append(_finding(f"Edge/origin region: {region}", "Inferred from the provider's request-id header.", "info", delivery.get("region_hint", "")[:40]))
    if delivery.get("powered_by"):
        findings.append(_finding("Runtime disclosed", f"An X-Powered-By header reveals the stack: {delivery['powered_by']}.", "warn", f"x-powered-by: {delivery['powered_by']}"))

    return {
        "summary": f"Rendering strategy inferred as {strategy}, with deployment fingerprints from response headers.",
        "confidence": 80,
        "strategy": strategy,
        "region": region,
        "findings": findings,
        "metrics": [
            {"label": "Strategy", "value": strategy},
            {"label": "Region", "value": region or "Unknown"},
            {"label": "Build id", "value": (str(nd.get("build_id"))[:10] if nd and nd.get("build_id") else "—")},
        ],
    }


# ---------------------------------------------------------------------------
# SEO & structured data
# ---------------------------------------------------------------------------
def analyze_seo(pages: list[dict], probes: dict | None = None) -> dict:
    page = _primary(pages)
    findings: list[dict] = []
    score = 45
    probes = probes or {}

    title = page.get("title") or ""
    if title:
        ok = 15 <= len(title) <= 65
        findings.append(_finding("Title tag", f"“{title[:80]}” ({len(title)} chars)" + ("" if ok else " — outside the ideal 15–65 range."), "good" if ok else "warn", title[:90]))
        score += 10
    else:
        findings.append(_finding("Missing title", "No <title> was found.", "bad", ""))

    desc = page.get("meta_description")
    if desc:
        findings.append(_finding("Meta description", f"{len(desc)} characters.", "good" if 50 <= len(desc) <= 165 else "warn", desc[:100]))
        score += 8
    else:
        findings.append(_finding("No meta description", "Search snippets will be auto-generated.", "warn", ""))

    og = page.get("open_graph", {})
    tw = page.get("twitter", {})
    if og:
        findings.append(_finding("Open Graph tags", f"{len(og)} OG properties power rich link previews ({', '.join(list(og)[:4])}).", "good", ", ".join(f"og:{k}" for k in list(og)[:6])))
        score += 8
    else:
        findings.append(_finding("No Open Graph", "Shared links won't render rich previews.", "warn", ""))
    if tw:
        findings.append(_finding("Twitter Card", f"Card type: {tw.get('card', 'present')}.", "good", ", ".join(f"twitter:{k}" for k in list(tw)[:4])))
        score += 4

    schemas = page.get("jsonld_types", [])
    if schemas:
        findings.append(_finding("Structured data (JSON-LD)", f"Schema.org types help search understand the page: {', '.join(schemas[:6])}.", "good", ", ".join(schemas[:8])))
        score += 12
    else:
        findings.append(_finding("No structured data", "No JSON-LD schema.org markup detected.", "info", ""))

    locales = set()
    for p in pages:
        locales.update(p.get("hreflangs", []))
    if locales:
        findings.append(_finding("Internationalized", f"{len(locales)} hreflang locales indicate a multi-region audience.", "good", ", ".join(sorted(locales)[:8])))
        score += 6
    if page.get("canonical"):
        score += 4
    if page.get("viewport"):
        findings.append(_finding("Mobile viewport", "A responsive viewport meta tag is set.", "good", page["viewport"][:60]))
        score += 3

    # Crawlability from robots.txt + sitemap probes.
    robots = probes.get("robots", {})
    sitemap = probes.get("sitemap", {})
    metrics = [
        {"label": "Schema types", "value": str(len(schemas))},
        {"label": "OG tags", "value": str(len(og))},
        {"label": "Locales", "value": str(len(locales))},
    ]
    if robots.get("present"):
        score += 4
        if robots.get("sample_disallows"):
            findings.append(_finding(
                "robots.txt disallow rules",
                f"{robots['disallow_count']} disallowed path(s), e.g. {', '.join(robots['sample_disallows'][:4])} — these hint at internal or non-public areas.",
                "info",
                ", ".join(robots["sample_disallows"][:6]),
            ))
        if robots.get("blocks_ai_bots"):
            findings.append(_finding(
                "Blocks AI crawlers",
                f"robots.txt explicitly disallows {len(robots['blocks_ai_bots'])} AI/LLM crawler(s): {', '.join(robots['blocks_ai_bots'][:6])}.",
                "info",
                ", ".join(robots["blocks_ai_bots"]),
            ))
    else:
        findings.append(_finding("No robots.txt", "No robots.txt was served; crawlers use defaults.", "info", ""))
    if sitemap.get("present"):
        findings.append(_finding(
            f"Sitemap ({sitemap.get('kind', 'sitemap')})",
            f"A sitemap lists {sitemap.get('entry_count', 0)} entr{'y' if sitemap.get('entry_count') == 1 else 'ies'}, aiding crawl coverage.",
            "good",
            sitemap.get("url", ""),
        ))
        score += 5
        metrics.append({"label": "Sitemap URLs", "value": str(sitemap.get("entry_count", 0))})

    score = min(100, score)
    return {
        "summary": f"SEO, structured data, and crawlability graded {_grade(score)} from metadata, sitemaps, and robots rules.",
        "confidence": 88,
        "grade": _grade(score),
        "score": score,
        "findings": findings,
        "metrics": metrics,
    }


# ---------------------------------------------------------------------------
# Privacy & third-party footprint
# ---------------------------------------------------------------------------
_TRACKER_HINTS = {
    "google-analytics": "Google Analytics", "googletagmanager": "Google Tag Manager", "doubleclick": "Google Ads",
    "facebook": "Meta Pixel", "hotjar": "Hotjar", "segment": "Segment", "mixpanel": "Mixpanel",
    "amplitude": "Amplitude", "posthog": "PostHog", "sentry": "Sentry", "intercom": "Intercom",
    "hubspot": "HubSpot", "onetrust": "OneTrust (consent)", "cookiebot": "Cookiebot (consent)",
}


def analyze_domain(probes: dict) -> dict | None:
    dns = probes.get("dns", {})
    redirect = probes.get("redirect", {})
    security_txt = probes.get("security_txt", {})
    if not dns.get("available"):
        return None

    findings: list[dict] = []
    score = 45

    if dns.get("email_provider"):
        findings.append(_finding("Email provider", f"MX records point to {dns['email_provider']} ({dns.get('mx_count', 0)} MX host(s)).", "info", f"{dns.get('mx_count', 0)} MX records"))
    dmarc = dns.get("dmarc_policy")
    if dmarc in {"reject", "quarantine"}:
        findings.append(_finding("DMARC enforced", f"A DMARC policy of p={dmarc} actively fights email spoofing of this domain.", "good", f"v=DMARC1; p={dmarc}"))
        score += 20 if dmarc == "reject" else 14
    elif dmarc == "none":
        findings.append(_finding("DMARC monitor-only", "A DMARC record exists but p=none only reports — it does not block spoofed mail.", "warn", "v=DMARC1; p=none"))
        score += 6
    else:
        findings.append(_finding("No DMARC policy", "No DMARC record was found; the domain is more exposed to email spoofing.", "warn", "_dmarc TXT: (absent)"))

    if dns.get("has_spf"):
        senders = dns.get("spf_senders", [])
        findings.append(_finding("SPF configured", "An SPF record authorizes approved senders" + (f": {', '.join(senders)}." if senders else "."), "good", ", ".join(senders) or "v=spf1"))
        score += 10
    else:
        findings.append(_finding("No SPF record", "No SPF record was found for the domain.", "warn", ""))

    if redirect.get("checked"):
        if redirect.get("redirects_to_https"):
            findings.append(_finding("HTTP → HTTPS redirect", f"Plain HTTP is redirected to HTTPS (status {redirect.get('status')}).", "good", f"http:// → {redirect.get('status')} https://"))
            score += 8
        else:
            findings.append(_finding("No HTTPS redirect", "Plain HTTP did not redirect to HTTPS on the initial request.", "warn", f"status {redirect.get('status')}"))

    if security_txt.get("present"):
        contact = security_txt.get("contact") or "a disclosure contact"
        findings.append(_finding("Publishes security.txt", f"A responsible-disclosure policy is published ({contact}).", "good", f"contact: {contact}"))
        score += 10
    else:
        findings.append(_finding("No security.txt", "No /.well-known/security.txt for coordinated vulnerability disclosure.", "info", ""))

    if dns.get("caa_issuers"):
        findings.append(_finding("CAA pinning", f"CAA records restrict certificate issuance to: {', '.join(dns['caa_issuers'])}.", "good", ", ".join(dns["caa_issuers"])))
        score += 5
    if dns.get("verified_tools"):
        findings.append(_finding("SaaS tools via DNS", f"Domain-verification TXT records reveal tools in use: {', '.join(dns['verified_tools'][:8])}.", "info", ", ".join(dns["verified_tools"])))

    metrics = [
        {"label": "Email", "value": dns.get("email_provider") or "Unknown"},
        {"label": "DMARC", "value": (dmarc or "none").title()},
        {"label": "DNS host", "value": dns.get("ns_provider") or "Unknown"},
        {"label": "SaaS tools", "value": str(len(dns.get("verified_tools", [])))},
    ]
    score = min(100, score)
    return {
        "summary": f"Domain, DNS, and email posture graded {_grade(score)} from MX/SPF/DMARC, redirect, security.txt, and CAA.",
        "confidence": 89,
        "grade": _grade(score),
        "score": score,
        "findings": findings,
        "metrics": metrics,
    }


def analyze_privacy(pages: list[dict]) -> dict:
    hosts: set[str] = set()
    for p in pages:
        hosts.update(p.get("third_party_hosts", []))
    all_cookies = [c for p in pages for c in p.get("cookies", [])]
    findings: list[dict] = []

    trackers = sorted({label for host in hosts for frag, label in _TRACKER_HINTS.items() if frag in host})
    consent = [t for t in trackers if "consent" in t]
    if trackers:
        findings.append(_finding("Third-party trackers", f"{len(trackers)} known analytics/marketing services observed: {', '.join(trackers[:6])}.", "warn" if not consent else "info", ", ".join(trackers)))
    if consent:
        findings.append(_finding("Consent management", f"A consent platform is present ({consent[0]}), suggesting GDPR/CCPA awareness.", "good", consent[0]))
    else:
        findings.append(_finding("No consent platform detected", "No OneTrust/Cookiebot-style consent manager was observed on the public surface.", "info", ""))

    findings.append(_finding("Third-party surface", f"The page contacts {len(hosts)} distinct third-party host(s).", "info" if len(hosts) < 12 else "warn", ", ".join(sorted(hosts)[:8])))

    insecure = [c for c in all_cookies if not c["secure"]]
    if all_cookies:
        findings.append(_finding("Cookie inventory", f"{len(all_cookies)} cookie(s) set; {len(insecure)} without the Secure flag.", "good" if not insecure else "warn", ", ".join(c["name"] for c in all_cookies[:5])))

    confidence = 84
    return {
        "summary": "Privacy footprint from third-party hosts, trackers, and cookie flags observed on public pages.",
        "confidence": confidence,
        "findings": findings,
        "metrics": [
            {"label": "Third-party hosts", "value": str(len(hosts))},
            {"label": "Known trackers", "value": str(len(trackers))},
            {"label": "Cookies", "value": str(len(all_cookies))},
        ],
    }
