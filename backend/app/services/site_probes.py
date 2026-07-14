"""Host-level deep probes that go beyond a single page's HTML.

Three intelligence sources most tools never surface:
- **TLS/certificate** — issuer CA, validity window, wildcard scope, protocol, cipher.
- **JavaScript weight** — real transfer bytes of the shipped bundles and whether
  source maps are publicly exposed (which leaks original source).
- **Crawlability** — robots.txt disallow rules (often reveal internal paths),
  which AI crawlers are blocked, and sitemap size.

Everything here is observable on public endpoints and fully evidence-backed.
"""

from __future__ import annotations

import asyncio
import re
import socket
import ssl
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

import httpx

# AI / LLM crawlers worth calling out when a site blocks (or allows) them.
_AI_BOTS = {
    "gptbot", "chatgpt-user", "oai-searchbot", "ccbot", "google-extended", "anthropic-ai",
    "claudebot", "claude-web", "perplexitybot", "bytespider", "amazonbot", "applebot-extended",
    "cohere-ai", "diffbot", "imagesiftbot", "omgilibot", "facebookbot", "meta-externalagent",
}

# DNS record type name → numeric code (Google DoH returns numeric types).
_DNS_TYPES = {"A": 1, "NS": 2, "MX": 15, "TXT": 16, "AAAA": 28, "CAA": 257}

# MX hostname fragment → email provider.
_MX_PROVIDERS = {
    "google": "Google Workspace", "googlemail": "Google Workspace", "outlook": "Microsoft 365",
    "protection.outlook": "Microsoft 365", "protonmail": "Proton Mail", "proton.me": "Proton Mail",
    "zoho": "Zoho Mail", "mailgun": "Mailgun", "sendgrid": "SendGrid", "amazonaws": "Amazon SES",
    "pphosted": "Proofpoint", "mimecast": "Mimecast", "messagingengine": "Fastmail",
    "yandex": "Yandex", "qq.com": "Tencent", "improvmx": "ImprovMX",
}
# SPF include: fragment → sending service.
_SPF_SENDERS = {
    "_spf.google.com": "Google", "spf.protection.outlook": "Microsoft 365", "sendgrid": "SendGrid",
    "mailgun": "Mailgun", "amazonses": "Amazon SES", "servers.mcsv.net": "Mailchimp",
    "_spf.salesforce": "Salesforce", "mail.zendesk": "Zendesk", "spf.mandrillapp": "Mandrill",
    "helpscout": "Help Scout", "sparkpostmail": "SparkPost", "_spf.intercom": "Intercom",
    "stripe.com": "Stripe", "spf.hubspotemail": "HubSpot", "customeriomail": "Customer.io",
    "_spf.createsend": "Campaign Monitor", "pardot": "Pardot", "postmarkapp": "Postmark",
}
# DNS TXT verification-token prefix → the SaaS tool it proves is in use.
_VERIFICATION_TOKENS = {
    "google-site-verification": "Google Search Console", "facebook-domain-verification": "Meta / Facebook",
    "apple-domain-verification": "Apple", "stripe-verification": "Stripe", "atlassian-domain-verification": "Atlassian",
    "docusign": "DocuSign", "adobe-idp-site-verification": "Adobe", "notion": "Notion", "miro-verification": "Miro",
    "zoom-domain-verification": "Zoom", "dropbox-domain-verification": "Dropbox", "shopify": "Shopify",
    "canva-site-verification": "Canva", "cloudflare-verify": "Cloudflare", "loom-site-verification": "Loom",
    "openai-domain-verification": "OpenAI", "webexdomainverification": "Webex", "asv=": "Apple",
    "ms=": "Microsoft 365", "onetrust": "OneTrust", "citrix": "Citrix", "logmein": "GoTo",
}
# Nameserver fragment → DNS provider.
_NS_PROVIDERS = {
    "cloudflare": "Cloudflare", "awsdns": "AWS Route 53", "googledomains": "Google Cloud DNS",
    "google.com": "Google Cloud DNS", "azure-dns": "Azure DNS", "nsone": "NS1", "dnsimple": "DNSimple",
    "domaincontrol": "GoDaddy", "registrar-servers": "Namecheap", "vercel-dns": "Vercel", "netlify": "Netlify",
    "digitalocean": "DigitalOcean", "name-services": "eNom", "dns.he.net": "Hurricane Electric",
}


# ---------------------------------------------------------------------------
# TLS / certificate
# ---------------------------------------------------------------------------
def _parse_cert_datetime(value: str) -> datetime:
    cleaned = re.sub(r"\s+", " ", value.replace(" GMT", "")).strip()
    return datetime.strptime(cleaned, "%b %d %H:%M:%S %Y").replace(tzinfo=timezone.utc)


def _rdn_value(rdn_sequence, key: str) -> str | None:
    for rdn in rdn_sequence or ():
        for attr, val in rdn:
            if attr == key:
                return val
    return None


def _tls_probe_sync(host: str) -> dict:
    context = ssl.create_default_context()
    with socket.create_connection((host, 443), timeout=8) as sock:
        with context.wrap_socket(sock, server_hostname=host) as ssock:
            cert = ssock.getpeercert()
            version = ssock.version()
            cipher = ssock.cipher()

    sans = [v for (t, v) in cert.get("subjectAltName", ()) if t == "DNS"]
    not_before = _parse_cert_datetime(cert["notBefore"])
    not_after = _parse_cert_datetime(cert["notAfter"])
    now = datetime.now(timezone.utc)
    issuer_org = _rdn_value(cert.get("issuer"), "organizationName") or _rdn_value(cert.get("issuer"), "commonName")
    return {
        "available": True,
        "protocol": version,
        "cipher": cipher[0] if cipher else None,
        "cipher_bits": cipher[2] if cipher else None,
        "issuer": issuer_org,
        "subject_cn": _rdn_value(cert.get("subject"), "commonName"),
        "san_count": len(sans),
        "wildcard": any(s.startswith("*.") for s in sans),
        "valid_from": not_before.isoformat(),
        "valid_until": not_after.isoformat(),
        "days_until_expiry": (not_after - now).days,
        "lifetime_days": (not_after - not_before).days,
    }


async def probe_tls(host: str) -> dict:
    try:
        return await asyncio.get_running_loop().run_in_executor(None, _tls_probe_sync, host)
    except Exception as error:
        return {"available": False, "error": type(error).__name__}


# ---------------------------------------------------------------------------
# JavaScript bundle weight + source-map exposure
# ---------------------------------------------------------------------------
async def _asset_size(client: httpx.AsyncClient, url: str) -> int | None:
    try:
        response = await client.head(url, follow_redirects=True)
        if response.status_code >= 400 or "content-length" not in response.headers:
            response = await client.get(url, follow_redirects=True)
        length = response.headers.get("content-length")
        return int(length) if length else (len(response.content) if response.request.method == "GET" else None)
    except (httpx.HTTPError, ValueError):
        return None


async def _sourcemap_exposed(client: httpx.AsyncClient, url: str) -> bool:
    try:
        response = await client.head(f"{url}.map", follow_redirects=True)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


async def probe_bundles(client: httpx.AsyncClient, script_urls: list[str]) -> dict:
    scripts = [u for u in dict.fromkeys(script_urls) if urlsplit(u).scheme in {"http", "https"}][:14]
    if not scripts:
        return {"available": False}
    sizes = await asyncio.gather(*[_asset_size(client, u) for u in scripts])
    sized = [(u, s) for u, s in zip(scripts, sizes) if s]
    total = sum(s for _, s in sized)
    largest = max(sized, key=lambda x: x[1], default=(None, 0))

    # Only probe likely first-party app bundles for exposed maps (cap the work).
    app_scripts = [u for u in scripts if "/_next/" in u or "/static/" in u or "/assets/" in u][:5] or scripts[:3]
    maps = await asyncio.gather(*[_sourcemap_exposed(client, u) for u in app_scripts])
    return {
        "available": True,
        "analyzed": len(sized),
        "total_bytes": total,
        "largest_url": largest[0],
        "largest_bytes": largest[1],
        "sourcemaps_exposed": sum(maps),
    }


# ---------------------------------------------------------------------------
# robots.txt + sitemap
# ---------------------------------------------------------------------------
async def probe_robots(client: httpx.AsyncClient, base: str) -> dict:
    try:
        response = await client.get(urljoin(base, "/robots.txt"), follow_redirects=True)
    except httpx.HTTPError:
        return {"present": False}
    if response.status_code >= 400 or "html" in response.headers.get("content-type", ""):
        return {"present": False}

    text = response.text[:20000]
    disallows: list[str] = []
    sitemaps: list[str] = []
    blocked_ai: set[str] = set()
    current_agents: list[str] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field, value = field.strip().lower(), value.strip()
        if field == "user-agent":
            current_agents = [value.lower()]
        elif field == "disallow" and value:
            disallows.append(value)
            for agent in current_agents:
                if agent in _AI_BOTS:
                    blocked_ai.add(agent)
        elif field == "sitemap":
            sitemaps.append(value)
    return {
        "present": True,
        "bytes": len(response.text),
        "disallow_count": len(disallows),
        "sample_disallows": list(dict.fromkeys(disallows))[:8],
        "sitemaps": sitemaps[:5],
        "blocks_ai_bots": sorted(blocked_ai),
    }


async def probe_sitemap(client: httpx.AsyncClient, base: str, robots_sitemaps: list[str]) -> dict:
    candidate = robots_sitemaps[0] if robots_sitemaps else urljoin(base, "/sitemap.xml")
    try:
        response = await client.get(candidate, follow_redirects=True)
    except httpx.HTTPError:
        return {"present": False}
    if response.status_code >= 400:
        return {"present": False}
    body = response.text
    is_index = "<sitemapindex" in body
    url_count = len(re.findall(r"<loc>", body))
    return {
        "present": True,
        "url": str(response.url),
        "is_index": is_index,
        "entry_count": url_count,
        "kind": "sitemap index" if is_index else "url set",
    }


# ---------------------------------------------------------------------------
# DNS + email posture (via DNS-over-HTTPS — no resolver dependency)
# ---------------------------------------------------------------------------
async def _doh(client: httpx.AsyncClient, name: str, rtype: str) -> list[str]:
    try:
        response = await client.get(
            "https://dns.google/resolve",
            params={"name": name, "type": rtype},
            headers={"accept": "application/dns-json"},
        )
        answers = response.json().get("Answer", [])
    except (httpx.HTTPError, ValueError):
        return []
    code = _DNS_TYPES.get(rtype)
    return [a["data"].strip('"') for a in answers if a.get("type") == code and a.get("data")]


def _match(value: str, table: dict[str, str]) -> str | None:
    low = value.lower()
    return next((label for frag, label in table.items() if frag in low), None)


async def probe_dns(client: httpx.AsyncClient, host: str) -> dict:
    mx, txt, ns, caa, dmarc_txt = await asyncio.gather(
        _doh(client, host, "MX"),
        _doh(client, host, "TXT"),
        _doh(client, host, "NS"),
        _doh(client, host, "CAA"),
        _doh(client, f"_dmarc.{host}", "TXT"),
    )
    email_provider = next((p for m in mx if (p := _match(m, _MX_PROVIDERS))), None)
    ns_provider = next((p for n in ns if (p := _match(n, _NS_PROVIDERS))), None)

    spf = next((t for t in txt if t.lower().startswith("v=spf1")), None)
    senders = sorted({label for t in txt for frag, label in _SPF_SENDERS.items() if frag in t.lower()}) if spf else []
    tools = sorted({label for t in txt for frag, label in _VERIFICATION_TOKENS.items() if t.lower().startswith(frag) or frag in t.lower()[:40]})

    dmarc = next((t for t in dmarc_txt if "v=dmarc1" in t.lower()), None)
    dmarc_policy = None
    if dmarc:
        match = re.search(r"p=(\w+)", dmarc)
        dmarc_policy = match.group(1).lower() if match else "none"

    caa_issuers = sorted({re.sub(r'^\d+\s+issue\w*\s+"?', "", c).strip('" ').split(";")[0] for c in caa if "issue" in c.lower()})
    return {
        "available": bool(mx or txt or ns),
        "mx_count": len(mx),
        "email_provider": email_provider,
        "ns_provider": ns_provider,
        "has_spf": bool(spf),
        "spf_senders": senders,
        "dmarc_policy": dmarc_policy,
        "verified_tools": tools[:12],
        "caa_issuers": [c for c in caa_issuers if c][:6],
    }


async def probe_http_redirect(client: httpx.AsyncClient, host: str) -> dict:
    try:
        response = await client.get(f"http://{host}/", follow_redirects=False)
    except httpx.HTTPError:
        return {"checked": False}
    location = response.headers.get("location", "")
    return {
        "checked": True,
        "status": response.status_code,
        "redirects_to_https": response.status_code in {301, 302, 307, 308} and location.startswith("https://"),
    }


async def probe_security_txt(client: httpx.AsyncClient, base: str) -> dict:
    for path in ("/.well-known/security.txt", "/security.txt"):
        try:
            response = await client.get(urljoin(base, path), follow_redirects=True)
        except httpx.HTTPError:
            continue
        if response.status_code != 200 or "html" in response.headers.get("content-type", ""):
            continue
        fields: dict[str, str] = {}
        for line in response.text[:5000].splitlines():
            if ":" in line and not line.strip().startswith("#"):
                key, _, value = line.partition(":")
                fields.setdefault(key.strip().lower(), value.strip())
        return {
            "present": True,
            "contact": fields.get("contact"),
            "expires": fields.get("expires"),
            "has_policy": "policy" in fields,
        }
    return {"present": False}


# ---------------------------------------------------------------------------
# API surface discovery (OpenAPI + GraphQL introspection)
# ---------------------------------------------------------------------------
_OPENAPI_PATHS = (
    "/openapi.json", "/swagger.json", "/api/openapi.json", "/v1/openapi.json",
    "/api-docs", "/api/swagger.json", "/swagger/v1/swagger.json", "/docs/openapi.json",
)
_GRAPHQL_PATHS = ("/graphql", "/api/graphql", "/v1/graphql", "/query")
_INTROSPECTION = '{"query":"query{__schema{queryType{name} mutationType{name} types{name kind}}}"}'


async def _fetch_openapi(client: httpx.AsyncClient, base: str) -> dict | None:
    for path in _OPENAPI_PATHS:
        try:
            response = await client.get(urljoin(base, path), follow_redirects=True)
        except httpx.HTTPError:
            continue
        if response.status_code != 200:
            continue
        try:
            spec = response.json()
        except ValueError:
            continue
        if not isinstance(spec, dict) or not (spec.get("openapi") or spec.get("swagger")) or "paths" not in spec:
            continue
        paths = spec.get("paths", {})
        operations = []
        for p, methods in list(paths.items())[:40]:
            if isinstance(methods, dict):
                for method in methods:
                    if method.lower() in {"get", "post", "put", "patch", "delete"}:
                        operations.append({"method": method.upper(), "path": p})
        info = spec.get("info", {})
        return {
            "url": str(response.url),
            "title": info.get("title"),
            "version": info.get("version"),
            "spec_version": spec.get("openapi") or spec.get("swagger"),
            "path_count": len(paths),
            "operations": operations[:12],
            "servers": [s.get("url") for s in spec.get("servers", []) if isinstance(s, dict)][:3],
        }
    return None


async def _probe_graphql(client: httpx.AsyncClient, base: str) -> dict | None:
    for path in _GRAPHQL_PATHS:
        url = urljoin(base, path)
        try:
            response = await client.post(url, content=_INTROSPECTION, headers={"content-type": "application/json"})
        except httpx.HTTPError:
            continue
        if response.status_code not in {200, 400}:
            continue
        try:
            data = response.json()
        except ValueError:
            continue
        schema = (data.get("data") or {}).get("__schema") if isinstance(data, dict) else None
        if schema:
            types = schema.get("types", []) or []
            return {
                "endpoint": url,
                "introspection_enabled": True,
                "query_type": (schema.get("queryType") or {}).get("name"),
                "mutation_type": (schema.get("mutationType") or {}).get("name"),
                "type_count": len([t for t in types if not str(t.get("name", "")).startswith("__")]),
            }
        # A GraphQL error for a valid endpoint still confirms GraphQL is present.
        if isinstance(data, dict) and "errors" in data:
            return {"endpoint": url, "introspection_enabled": False}
    return None


async def probe_api(client: httpx.AsyncClient, base: str) -> dict:
    openapi, graphql = await asyncio.gather(_fetch_openapi(client, base), _probe_graphql(client, base))
    return {"openapi": openapi, "graphql": graphql}


# ---------------------------------------------------------------------------
# .well-known: mobile app associations + ads
# ---------------------------------------------------------------------------
async def _json_at(client: httpx.AsyncClient, url: str):
    try:
        response = await client.get(url, follow_redirects=True)
        if response.status_code != 200:
            return None
        return response.json()
    except (httpx.HTTPError, ValueError):
        return None


async def probe_wellknown(client: httpx.AsyncClient, base: str) -> dict:
    aasa = await _json_at(client, urljoin(base, "/.well-known/apple-app-site-association")) \
        or await _json_at(client, urljoin(base, "/apple-app-site-association"))
    assetlinks = await _json_at(client, urljoin(base, "/.well-known/assetlinks.json"))

    ios_ids: list[str] = []
    if isinstance(aasa, dict):
        applinks = aasa.get("applinks", {})
        for detail in (applinks.get("details") or []):
            if isinstance(detail, dict):
                ios_ids.extend(detail.get("appIDs") or ([detail["appID"]] if detail.get("appID") else []))
    android_pkgs: list[str] = []
    if isinstance(assetlinks, list):
        for entry in assetlinks:
            target = entry.get("target", {}) if isinstance(entry, dict) else {}
            if target.get("package_name"):
                android_pkgs.append(target["package_name"])

    return {
        "ios_app": bool(ios_ids),
        "android_app": bool(android_pkgs),
        "ios_app_ids": list(dict.fromkeys(ios_ids))[:5],
        "android_packages": list(dict.fromkeys(android_pkgs))[:5],
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
async def run_site_probes(target_url: str, script_urls: list[str]) -> dict:
    host = (urlsplit(target_url).hostname or "").lower()
    base = f"{urlsplit(target_url).scheme}://{host}"
    async with httpx.AsyncClient(
        timeout=15, headers={"User-Agent": "OrbitBot/0.1 (+https://orbit.dev; software-intelligence)"}
    ) as client:
        tls, bundles, robots, dns, redirect, security_txt, api, wellknown = await asyncio.gather(
            probe_tls(host),
            probe_bundles(client, script_urls),
            probe_robots(client, base),
            probe_dns(client, host),
            probe_http_redirect(client, host),
            probe_security_txt(client, base),
            probe_api(client, base),
            probe_wellknown(client, base),
        )
        sitemap = await probe_sitemap(client, base, robots.get("sitemaps", []))
    return {
        "tls": tls, "bundles": bundles, "robots": robots, "sitemap": sitemap,
        "dns": dns, "redirect": redirect, "security_txt": security_txt,
        "api": api, "wellknown": wellknown,
    }
