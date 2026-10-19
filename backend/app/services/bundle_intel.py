"""Client-code intelligence: read the public JavaScript a product ships.

Every visitor's browser downloads these bundles, so reading them stays inside Orbit's
public-surface boundary. Orbit extracts *references* and never executes the code:

- API endpoints, GraphQL operation names, and realtime channels named in the code
- client routes from framework build manifests, chunk names, and router configs
- feature-flag keys passed to known flag SDKs
- libraries identified by strings that survive minification
- public client keys (masked) and secret-like strings (masked, never stored in full)
- when a source map is publicly reachable: the original file tree and dependency list,
  never the source contents themselves
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import re
import socket
from collections import Counter
from collections.abc import Awaitable, Callable
from urllib.parse import urljoin, urlsplit

import httpx

MAX_SCRIPTS = 24
MAX_SCRIPT_BYTES = 4 * 1024 * 1024
MAX_TOTAL_SCRIPT_BYTES = 16 * 1024 * 1024
FETCH_CONCURRENCY = 6
MAX_MAPS = 2
MAX_MAP_BYTES = 25 * 1024 * 1024

_LIMITS = {"endpoints": 60, "graphql_operations": 40, "realtime": 10, "routes": 80, "flags": 40}

_FIRST_PARTY_PATH_HINTS = ("/_next/static/", "/assets/", "/static/js/", "/build/", "/dist/")
# Runtime chunks rarely name product endpoints, so they are read last.
_FRAMEWORK_CHUNK = re.compile(r"/(?:framework|webpack|turbopack|polyfills|main-app|react-refresh|vendors?)[-.]", re.I)
_THIRD_PARTY_HOSTS = (
    "googletagmanager.com", "google-analytics.com", "doubleclick.net", "facebook.net", "hotjar.com",
    "segment.com", "intercom.io", "intercomcdn.com", "hs-scripts.com", "cloudflareinsights.com",
    "sentry-cdn.com", "stripe.com", "recaptcha.net", "gstatic.com", "youtube.com", "vimeo.com",
)

_ENDPOINT = re.compile(
    r"""["'`](/(?:api|v\d{1,2}|graphql|gql|rest|rpc|trpc|internal|_api|ajax|services?)"""
    r"""(?:/[A-Za-z0-9_\-.:{}$]{0,80}){0,10})["'`?]"""
)
_ABSOLUTE_URL = re.compile(r"""["'`]((?:https?|wss?)://[a-z0-9.-]{3,120}(?::\d{2,5})?(?:/[^"'`\s<>\\]{0,200})?)["'`]""", re.I)
_METHOD_AFTER = re.compile(r"""method\s*:\s*["'`](GET|POST|PUT|PATCH|DELETE)["'`]""", re.I)
_METHOD_BEFORE = re.compile(r"""\.(get|post|put|patch|delete)\(\s*$""", re.I)
_TEMPLATE_PARAM = re.compile(r"\$\{[^}]{0,60}\}|\{[A-Za-z_][\w]{0,40}\}")
_STATIC_ASSET = re.compile(r"\.(?:js|mjs|css|map|png|jpe?g|gif|svg|webp|avif|ico|woff2?|ttf|otf|mp4|webm|txt|html?)(?:$|\?)", re.I)

_GRAPHQL_OPERATION = re.compile(r"\b(query|mutation|subscription)\s+([A-Z][A-Za-z0-9_]{2,60})\s*[({]")
_OPERATION_NAME = re.compile(r"""operationName\s*:\s*["'`]([A-Z][A-Za-z0-9_]{2,60})["'`]""")

_FLAG_KEY = r"""\(\s*["'`]([A-Za-z0-9][\w.:\-]{1,80})["'`]"""
_FLAG_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\.variation" + _FLAG_KEY), "LaunchDarkly"),
    (re.compile(r"\b(?:checkGate|useGate|getFeatureGate|getExperiment|useExperiment)" + _FLAG_KEY), "Statsig"),
    (re.compile(r"\b(?:useFeatureIsOn|useFeatureValue|getFeatureValue)" + _FLAG_KEY), "GrowthBook"),
    (re.compile(r"\.isOn" + _FLAG_KEY), "GrowthBook"),
    (re.compile(r"\b(?:isFeatureEnabled|getFeatureFlag|useFeatureFlagEnabled|useFeatureFlagVariantKey|useFeatureFlagPayload)" + _FLAG_KEY), "PostHog"),
    (re.compile(r"\bgetTreatment" + _FLAG_KEY), "Split"),
    (re.compile(r"\.decide" + _FLAG_KEY), "Optimizely"),
    (re.compile(r"\b(?:useFeatureFlag|useFlag|isFlagEnabled|featureEnabled)" + _FLAG_KEY), "Feature flag"),
]

# Strings that survive minification and identify a bundled library.
_LIBRARY_MARKERS: dict[str, tuple[str, ...]] = {
    "React": ('Symbol.for("react.', "Symbol.for('react."),
    "Vue": ("__VUE__", "__vue_app__"),
    "Angular": ("ng-version", "@angular/core"),
    "Svelte": ("__svelte",),
    "Redux": ("@@redux/INIT",),
    "Apollo Client": ("ApolloClient", "@apollo/client"),
    "Relay": ("relay-runtime",),
    "urql": ("@urql/",),
    "Zod": ("ZodError",),
    "Socket.IO": ("socket.io",),
    "Pusher": ("pusher.com", "pusherapp.com"),
    "Ably": ("realtime.ably", "ably.io"),
    "Liveblocks": ("liveblocks",),
    "Yjs (CRDT)": ("y-protocols", "y-websocket"),
    "ProseMirror": ("ProseMirror",),
    "TipTap": ("@tiptap/",),
    "Lexical": ("__lexical",),
    "Firebase": ("firebaseio.com", "@firebase/"),
    "Supabase": ("supabase.co", "@supabase/"),
    "Algolia": ("algolianet.com", "algolia.net"),
    "Mapbox": ("api.mapbox.com", "mapbox-gl"),
    "Stripe.js": ("js.stripe.com", "@stripe/stripe-js"),
    "Sentry": ("__SENTRY__", "@sentry/", "ingest.sentry.io"),
    "Datadog RUM": ("browser-intake-datadoghq", "@datadog/browser-rum"),
    "PostHog": ("posthog",),
    "Amplitude": ("api2.amplitude.com", "@amplitude/"),
    "Mixpanel": ("api-js.mixpanel.com", "mixpanel-browser"),
    "Segment": ("cdn.segment.com", "@segment/analytics"),
    "LaunchDarkly": ("launchdarkly",),
    "Statsig": ("featuregates.org", "statsigapi"),
    "GrowthBook": ("growthbook",),
    "Intercom": ("widget.intercom.io",),
    "Auth0": ("auth0.com",),
    "Clerk": ("clerk.accounts", "@clerk/"),
}

# Keys that are public by design: reported as info, masked.
_PUBLIC_KEYS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bpk_(?:live|test)_[A-Za-z0-9]{16,}"), "Stripe publishable key"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "Google API key"),
    (re.compile(r"https://[0-9a-f]{32}@[a-z0-9.\-]*sentry\.io/\d+"), "Sentry DSN"),
    (re.compile(r"\bpk\.eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}"), "Mapbox public token"),
]
# Credentials that should never ship to a browser: reported as bad, masked, never stored whole.
_SECRETS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(?:sk|rk)_live_[A-Za-z0-9]{16,}"), "Stripe secret key"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key ID"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}"), "GitHub token"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"), "Slack token"),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}"), "Anthropic API key"),
    (re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{32,}"), "OpenAI API key"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"), "Private key block"),
]

_NON_PRODUCTION_LABELS = {
    "staging", "stage", "stg", "dev", "develop", "development", "qa", "uat", "sandbox",
    "test", "testing", "preprod", "internal", "intranet",
}

_MANIFEST_ROUTE = re.compile(r"""["'](/[^"'\s]{0,150})["']\s*:\s*\[""")
_ROUTER_PATH = re.compile(r"""\bpath\s*:\s*["'](/[A-Za-z0-9_\-/:.*\[\]]{1,120})["']""")
_APP_CHUNK = re.compile(r"/_next/static/chunks/app/(.+?)/page-[0-9a-f]+\.js")
_PAGES_CHUNK = re.compile(r"/_next/static/chunks/pages/(.+?)-[0-9a-f]+\.js")
_BUILD_MANIFEST_URL = re.compile(r"/_next/static/([^/]+)/_buildManifest\.js")
_SOURCE_MAPPING_URL = re.compile(r"//[#@]\s*sourceMappingURL=([^\s'\"]+)\s*$")
_FRAMEWORK_ROUTES = {"/_app", "/_error", "/_document", "/404", "/500", "/_not-found"}

Resolver = Callable[[str], Awaitable[bool]]


# ---------------------------------------------------------------------------
# Pure extraction (testable without the network)
# ---------------------------------------------------------------------------
def _registrable(host: str) -> str:
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _is_first_party_host(host: str, target_host: str) -> bool:
    suffix = _registrable(target_host)
    return host == target_host or host == suffix or host.endswith(f".{suffix}")


def normalize_endpoint(path: str) -> str:
    """Keep the route shape; replace template parameters and identifiers with :param."""
    path = _TEMPLATE_PARAM.sub(":param", path.split("?")[0])
    segments = []
    for segment in path.split("/"):
        if re.fullmatch(r"\d{2,}|[0-9a-f]{8}-[0-9a-f-]{27,}|(?=[A-Za-z_-]*\d)[A-Za-z0-9_-]{20,}", segment, re.I):
            segment = ":param"
        segments.append(segment)
    normalized = "/".join(segments).rstrip("/") or "/"
    return normalized[:160]


def _route_from_file(path: str) -> str:
    """Turn a framework file path (`(marketing)/[team]/settings`) into a route (`/:team/settings`)."""
    parts = []
    for part in path.split("/"):
        if not part or (part.startswith("(") and part.endswith(")")) or part.startswith("@"):
            continue
        if part == "index":
            continue
        part = re.sub(r"^\[\[?\.{3}([^\]]+)\]\]?$", r":\1*", part)
        part = re.sub(r"^\[([^\]]+)\]$", r":\1", part)
        parts.append(part)
    return "/" + "/".join(parts)


def mask_secret(value: str) -> str:
    return f"{value[:4]}…({len(value)} chars)"


def _method_near(source: str, start: int, end: int) -> str | None:
    before = source[max(0, start - 24):start]
    if (match := _METHOD_BEFORE.search(before)):
        return match.group(1).upper()
    if (match := _METHOD_AFTER.search(source[end:end + 160])):
        return match.group(1).upper()
    return None


def extract_code_signals(source: str, target_host: str) -> dict:
    """Extract references from one bundle's text. Values of secrets are never returned."""
    endpoints: dict[tuple[str, str], dict] = {}
    for match in _ENDPOINT.finditer(source):
        raw = match.group(1)
        if _STATIC_ASSET.search(raw):
            continue
        path = normalize_endpoint(raw)
        if path in {"/api", "/v1", "/v2"}:
            continue
        method = _method_near(source, match.start(), match.end()) or "ANY"
        key = (method, path)
        endpoints.setdefault(key, {"method": method, "path": path, "host": None})

    realtime: list[str] = []
    hosts: Counter[str] = Counter()
    for match in _ABSOLUTE_URL.finditer(source):
        url = match.group(1)
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if not host or "." not in host:
            continue
        hosts[host] += 1
        if parts.scheme.lower() in {"ws", "wss"}:
            channel = f"{parts.scheme.lower()}://{host}{normalize_endpoint(parts.path or '/') if parts.path else ''}"
            if channel not in realtime:
                realtime.append(channel)
            continue
        first_party = _is_first_party_host(host, target_host)
        api_like = host.startswith(("api.", "api-", "gql.", "graphql.")) or bool(
            re.match(r"/(?:api|v\d{1,2}|graphql|rest|rpc|trpc)(?:/|$)", parts.path or "")
        )
        if first_party and api_like and parts.path and not _STATIC_ASSET.search(parts.path):
            path = normalize_endpoint(parts.path)
            method = _method_near(source, match.start(), match.end()) or "ANY"
            endpoints.setdefault((method, f"{host}{path}"), {"method": method, "path": path, "host": host})

    operations: dict[str, str] = {}
    for match in _GRAPHQL_OPERATION.finditer(source):
        operations.setdefault(match.group(2), match.group(1))
    for match in _OPERATION_NAME.finditer(source):
        operations.setdefault(match.group(1), "operation")

    flags: dict[str, str] = {}
    for pattern, provider in _FLAG_PATTERNS:
        for match in pattern.finditer(source):
            flags.setdefault(match.group(1), provider)

    libraries = [name for name, markers in _LIBRARY_MARKERS.items() if any(m in source for m in markers)]

    public_keys: dict[str, str] = {}
    for pattern, kind in _PUBLIC_KEYS:
        for match in pattern.finditer(source):
            public_keys.setdefault(mask_secret(match.group(0)), kind)
    secrets: dict[str, str] = {}
    for pattern, kind in _SECRETS:
        for match in pattern.finditer(source):
            secrets.setdefault(mask_secret(match.group(0)), kind)

    routes = {route for route in (m.group(1) for m in _ROUTER_PATH.finditer(source)) if not _STATIC_ASSET.search(route)}

    first_party_hosts = sorted(h for h in hosts if _is_first_party_host(h, target_host))
    non_production = sorted(
        h for h in first_party_hosts if _NON_PRODUCTION_LABELS & set(re.split(r"[.\-]", h))
    )
    return {
        "endpoints": list(endpoints.values()),
        "realtime": realtime,
        "graphql_operations": [{"name": n, "kind": k} for n, k in operations.items()],
        "flags": [{"key": k, "provider": p} for k, p in flags.items()],
        "libraries": libraries,
        "public_keys": [{"kind": k, "masked": m} for m, k in public_keys.items()],
        "secrets": [{"kind": k, "masked": m} for m, k in secrets.items()],
        "routes": sorted(routes),
        "first_party_hosts": first_party_hosts,
        "non_production_hosts": non_production,
    }


def parse_build_manifest(source: str) -> list[str]:
    """Next.js `_buildManifest.js` maps every pages-router route to its chunks."""
    routes = []
    for match in _MANIFEST_ROUTE.finditer(source):
        route = match.group(1)
        if route in _FRAMEWORK_ROUTES or route.startswith("/_"):
            continue
        routes.append(_route_from_file(route.strip("/")) if "[" in route else route)
    return sorted(set(routes))


def routes_from_script_urls(script_urls: list[str]) -> list[str]:
    """Next.js chunk file names encode the route they render."""
    routes = set()
    for url in script_urls:
        path = urlsplit(url).path
        if (match := _APP_CHUNK.search(path)) or (match := _PAGES_CHUNK.search(path)):
            route = _route_from_file(match.group(1))
            if route not in _FRAMEWORK_ROUTES:
                routes.add(route)
    return sorted(routes)


def _clean_source_path(path: str) -> str:
    path = re.sub(r"^[a-z]+://(?:[^/]*/)?", "", path)
    path = path.split("?")[0]
    while path.startswith(("./", "../")):
        path = path[3:] if path.startswith("../") else path[2:]
    return path.lstrip("/")


def summarize_source_map(source_map: dict) -> dict:
    """File tree and dependency list from a source map. `sourcesContent` is never kept."""
    sources: list[str] = list(source_map.get("sources") or [])
    has_contents = bool(source_map.get("sourcesContent"))
    for section in source_map.get("sections") or []:
        inner = section.get("map") or {}
        sources.extend(inner.get("sources") or [])
        has_contents = has_contents or bool(inner.get("sourcesContent"))

    dependencies: set[str] = set()
    app_files: list[str] = []
    for raw in sources:
        if not isinstance(raw, str):
            continue
        path = _clean_source_path(raw)
        if not path or path.startswith(("webpack/", "(webpack)")):
            continue
        if "node_modules/" in path:
            tail = path.split("node_modules/")[-1].split("/")
            name = "/".join(tail[:2]) if tail[0].startswith("@") and len(tail) > 1 else tail[0]
            if name:
                dependencies.add(name)
            continue
        app_files.append(path)

    areas: Counter[str] = Counter()
    roots = {"src", "app", "pages", "lib", "client", "frontend", "web", "packages", "apps"}
    for path in app_files:
        segments = [s for s in path.split("/")[:-1] if s and s not in {".", ".."}]
        while segments and segments[0] in roots:
            segments = segments[1:]
        if segments:
            areas["/".join(segments[:2])] += 1
    extensions = Counter(p.rsplit(".", 1)[-1].lower() for p in app_files if "." in p.rsplit("/", 1)[-1])
    ts = extensions["ts"] + extensions["tsx"]
    js = extensions["js"] + extensions["jsx"] + extensions["mjs"]
    language = "TypeScript" if ts and ts >= js else "JavaScript" if js else None
    if extensions["vue"] > max(ts, js):
        language = "Vue SFC"
    elif extensions["svelte"] > max(ts, js):
        language = "Svelte"
    return {
        "files": len(sources),
        "app_files": len(app_files),
        "dependencies": sorted(dependencies),
        "areas": [{"area": area, "files": count} for area, count in areas.most_common(14)],
        "language": language,
        "sources_content": has_contents,
    }


def merge_signals(per_script: list[dict], routes: list[str]) -> dict:
    merged: dict = {
        "endpoints": {}, "realtime": [], "graphql_operations": {}, "flags": {}, "libraries": [],
        "public_keys": {}, "secrets": {}, "routes": set(routes), "first_party_hosts": set(), "non_production_hosts": set(),
    }
    for signals in per_script:
        for ep in signals["endpoints"]:
            merged["endpoints"].setdefault((ep.get("host") or "", ep["path"], ep["method"]), ep)
        merged["realtime"] += [c for c in signals["realtime"] if c not in merged["realtime"]]
        for op in signals["graphql_operations"]:
            merged["graphql_operations"].setdefault(op["name"], op["kind"])
        for flag in signals["flags"]:
            merged["flags"].setdefault(flag["key"], flag["provider"])
        merged["libraries"] += [lib for lib in signals["libraries"] if lib not in merged["libraries"]]
        for item in signals["public_keys"]:
            merged["public_keys"].setdefault(item["masked"], item["kind"])
        for item in signals["secrets"]:
            merged["secrets"].setdefault(item["masked"], item["kind"])
        merged["routes"].update(signals["routes"])
        merged["first_party_hosts"].update(signals["first_party_hosts"])
        merged["non_production_hosts"].update(signals["non_production_hosts"])

    # A bare reference ("ANY") adds nothing once the same path is seen with a concrete method.
    specific = {(host, path) for host, path, method in merged["endpoints"] if method != "ANY"}
    endpoints = sorted(
        (ep for (host, path, method), ep in merged["endpoints"].items() if method != "ANY" or (host, path) not in specific),
        key=lambda e: (e.get("host") or "", e["path"], e["method"]),
    )
    return {
        "endpoints": endpoints[:_LIMITS["endpoints"]],
        "endpoint_count": len(endpoints),
        "realtime": merged["realtime"][:_LIMITS["realtime"]],
        "graphql_operations": [{"name": n, "kind": k} for n, k in sorted(merged["graphql_operations"].items())][:_LIMITS["graphql_operations"]],
        "flags": [{"key": k, "provider": p} for k, p in sorted(merged["flags"].items())][:_LIMITS["flags"]],
        "flag_count": len(merged["flags"]),
        "libraries": merged["libraries"],
        "public_keys": [{"kind": k, "masked": m} for m, k in merged["public_keys"].items()],
        "secrets": [{"kind": k, "masked": m} for m, k in merged["secrets"].items()],
        "routes": sorted(merged["routes"])[:_LIMITS["routes"]],
        "route_count": len(merged["routes"]),
        "first_party_hosts": sorted(merged["first_party_hosts"])[:20],
        "non_production_hosts": sorted(merged["non_production_hosts"])[:10],
    }


# ---------------------------------------------------------------------------
# Fetching (bounded, public-network only)
# ---------------------------------------------------------------------------
async def resolves_publicly(host: str) -> bool:
    if not host or host == "localhost" or host.endswith(".local"):
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        pass
    try:
        infos = await asyncio.get_running_loop().run_in_executor(
            None, lambda: socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        )
    except OSError:
        return False
    return bool(infos) and all(ipaddress.ip_address(info[4][0]).is_global for info in infos)


async def _fetch_text(
    client: httpx.AsyncClient, url: str, limit: int, resolver: Resolver, *, allow_truncate: bool
) -> tuple[str | None, bool]:
    """GET a public URL with a byte cap. Returns (text, truncated). Redirects are not followed."""
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not await resolver((parts.hostname or "").lower()):
        return None, False
    try:
        async with client.stream("GET", url, follow_redirects=False) as response:
            if response.status_code != 200:
                return None, False
            declared = response.headers.get("content-length")
            if declared and declared.isdigit() and int(declared) > limit and not allow_truncate:
                return None, False
            chunks: list[bytes] = []
            size = 0
            truncated = False
            async for chunk in response.aiter_bytes():
                chunks.append(chunk)
                size += len(chunk)
                if size >= limit:
                    truncated = True
                    break
            if truncated and not allow_truncate:
                return None, False
            return b"".join(chunks)[:limit].decode("utf-8", errors="replace"), truncated
    except httpx.HTTPError:
        return None, False


def select_app_scripts(script_urls: list[str], target_host: str) -> list[str]:
    selected = []
    for url in dict.fromkeys(script_urls):
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if parts.scheme not in {"http", "https"} or any(host == t or host.endswith(f".{t}") for t in _THIRD_PARTY_HOSTS):
            continue
        if _is_first_party_host(host, target_host) or any(hint in parts.path for hint in _FIRST_PARTY_PATH_HINTS):
            selected.append(url)
    selected.sort(key=lambda u: bool(_FRAMEWORK_CHUNK.search(urlsplit(u).path)))  # stable: page order otherwise
    return selected[:MAX_SCRIPTS]


async def probe_code_intel(
    client: httpx.AsyncClient,
    script_urls: list[str],
    target_url: str,
    build_id: str | None = None,
    resolver: Resolver = resolves_publicly,
) -> dict:
    target_host = (urlsplit(target_url).hostname or "").lower()
    scripts = select_app_scripts(script_urls, target_host)
    if not scripts:
        return {"available": False, "reason": "No first-party JavaScript bundles were found on the page."}

    gate = asyncio.Semaphore(FETCH_CONCURRENCY)

    async def fetch(url: str) -> tuple[str | None, bool]:
        async with gate:
            return await _fetch_text(client, url, MAX_SCRIPT_BYTES, resolver, allow_truncate=True)

    fetched = await asyncio.gather(*[fetch(url) for url in scripts])
    per_script: list[dict] = []
    map_urls: list[str] = []
    bytes_analyzed = 0
    truncated = 0
    for url, (text, was_truncated) in zip(scripts, fetched):
        if text is None or bytes_analyzed >= MAX_TOTAL_SCRIPT_BYTES:
            continue
        bytes_analyzed += len(text)
        truncated += int(was_truncated)
        per_script.append(extract_code_signals(text, target_host))
        if (match := _SOURCE_MAPPING_URL.search(text[-600:])) and not match.group(1).startswith("data:"):
            map_urls.append(urljoin(url, match.group(1)))

    routes = routes_from_script_urls(script_urls)
    manifest_url = next((u for u in script_urls if _BUILD_MANIFEST_URL.search(urlsplit(u).path)), None)
    if manifest_url is None and build_id and re.fullmatch(r"[A-Za-z0-9_\-]{4,80}", build_id):
        parts = urlsplit(target_url)
        manifest_url = f"{parts.scheme}://{parts.netloc}/_next/static/{build_id}/_buildManifest.js"
    route_source = "chunk names" if routes else None
    if manifest_url:
        manifest, _ = await _fetch_text(client, manifest_url, 512 * 1024, resolver, allow_truncate=False)
        if manifest:
            manifest_routes = parse_build_manifest(manifest)
            if manifest_routes:
                routes = sorted(set(routes) | set(manifest_routes))
                route_source = "Next.js build manifest"

    source_maps = []
    for map_url in list(dict.fromkeys(map_urls))[:MAX_MAPS]:
        text, _ = await _fetch_text(client, map_url, MAX_MAP_BYTES, resolver, allow_truncate=False)
        if not text:
            continue
        try:
            parsed = json.loads(text)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            source_maps.append(summarize_source_map(parsed))

    if not per_script:
        return {"available": False, "reason": "First-party bundles could not be downloaded."}

    result = merge_signals(per_script, routes)
    result.update({
        "available": True,
        "scripts_analyzed": len(per_script),
        "bytes_analyzed": bytes_analyzed,
        "truncated_scripts": truncated,
        "route_source": route_source or ("router config" if result["routes"] else None),
        "source_map": _merge_maps(source_maps),
    })
    return result


def _merge_maps(maps: list[dict]) -> dict | None:
    if not maps:
        return None
    areas: Counter[str] = Counter()
    for item in maps:
        for area in item["areas"]:
            areas[area["area"]] += area["files"]
    dependencies = sorted({d for item in maps for d in item["dependencies"]})
    return {
        "maps": len(maps),
        "files": sum(m["files"] for m in maps),
        "app_files": sum(m["app_files"] for m in maps),
        "dependencies": dependencies[:60],
        "dependency_count": len(dependencies),
        "areas": [{"area": a, "files": n} for a, n in areas.most_common(14)],
        "language": next((m["language"] for m in maps if m["language"]), None),
        "sources_content": any(m["sources_content"] for m in maps),
    }
