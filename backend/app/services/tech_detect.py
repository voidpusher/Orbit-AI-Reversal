"""Signature-based technology detection over observed public signals.

Every detection is derived from *observable* evidence: third-party network hosts,
HTML/script markers, and response headers. Detections carry a category, a
confidence score, and the concrete evidence strings that triggered them so the
report can present them honestly rather than as unverifiable claims.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Signals:
    """Normalized, observable signals gathered across explored pages."""

    hosts: set[str] = field(default_factory=set)
    scripts: list[str] = field(default_factory=list)
    html_markers: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
    generators: list[str] = field(default_factory=list)

    def merge(self, other: "Signals") -> None:
        self.hosts |= other.hosts
        self.scripts.extend(other.scripts)
        self.html_markers.extend(other.html_markers)
        self.headers.update(other.headers)
        self.generators.extend(other.generators)


@dataclass
class Detection:
    name: str
    category: str
    confidence: int
    evidence: list[str]


# category, [host fragments], [script/html markers], [header (key,value-fragment)], base confidence
_SIGNATURES: list[tuple[str, str, list[str], list[str], list[tuple[str, str]], int]] = [
    # Frameworks
    ("Next.js", "Framework", [], ["/_next/", "__NEXT_DATA__", "next/dist"], [("x-powered-by", "next")], 92),
    ("React", "Frontend", [], ["react", "reactroot", "_reactlisteners", "data-reactroot"], [], 84),
    ("Vue.js", "Frontend", [], ["__vue__", "data-v-", "vue.runtime"], [], 82),
    ("Svelte", "Frontend", [], ["svelte-", "__svelte"], [], 80),
    ("Angular", "Frontend", [], ["ng-version", "angular"], [], 82),
    ("Nuxt", "Framework", [], ["__nuxt", "/_nuxt/"], [], 85),
    ("Gatsby", "Framework", [], ["___gatsby", "/page-data/"], [], 84),
    ("Remix", "Framework", [], ["__remixcontext", "remix"], [], 80),
    ("Astro", "Framework", [], ["astro-island", "data-astro"], [], 82),
    # Hosting / CDN / edge
    ("Vercel", "Hosting", ["vercel.app", "vercel-insights"], ["_vercel"], [("server", "vercel"), ("x-vercel-id", "")], 90),
    ("Netlify", "Hosting", ["netlify.app", "netlify.com"], [], [("server", "netlify")], 88),
    ("Cloudflare", "CDN", ["cloudflare", "cdn-cgi"], ["/cdn-cgi/"], [("server", "cloudflare"), ("cf-ray", "")], 90),
    ("AWS CloudFront", "CDN", ["cloudfront.net"], [], [("via", "cloudfront"), ("x-amz-cf-id", "")], 86),
    ("Fastly", "CDN", ["fastly.net"], [], [("x-served-by", "cache"), ("x-fastly", "")], 82),
    ("AWS", "Hosting", ["amazonaws.com", "s3.amazonaws"], [], [("x-amz-request-id", "")], 78),
    ("Google Cloud", "Hosting", ["googleusercontent", "appspot.com", "storage.googleapis"], [], [], 74),
    # Analytics
    ("Google Analytics", "Analytics", ["google-analytics.com", "googletagmanager.com"], ["gtag(", "ga("], [], 90),
    ("Segment", "Analytics", ["segment.com", "segment.io"], ["analytics.js"], [], 86),
    ("Amplitude", "Analytics", ["amplitude.com"], ["amplitude"], [], 84),
    ("Mixpanel", "Analytics", ["mixpanel.com"], ["mixpanel"], [], 84),
    ("PostHog", "Analytics", ["posthog.com", "i.posthog"], ["posthog"], [], 84),
    ("Plausible", "Analytics", ["plausible.io"], [], [], 82),
    ("Hotjar", "Analytics", ["hotjar.com"], ["hotjar"], [], 80),
    # Payments
    ("Stripe", "Payments", ["stripe.com", "js.stripe", "stripe.network"], ["stripe"], [], 92),
    ("Paddle", "Payments", ["paddle.com"], ["paddle"], [], 84),
    ("PayPal", "Payments", ["paypal.com", "paypalobjects"], ["paypal"], [], 82),
    ("Lemon Squeezy", "Payments", ["lemonsqueezy.com"], [], [], 82),
    # Monitoring
    ("Sentry", "Monitoring", ["sentry.io", "sentry-cdn"], ["sentry"], [], 88),
    ("Datadog", "Monitoring", ["datadoghq.com", "datadog-rum"], ["datadog"], [], 84),
    ("LogRocket", "Monitoring", ["logrocket.com"], ["logrocket"], [], 82),
    ("New Relic", "Monitoring", ["newrelic.com", "nr-data.net"], ["newrelic"], [], 82),
    # Auth
    ("Auth0", "Authentication", ["auth0.com"], ["auth0"], [], 88),
    ("Clerk", "Authentication", ["clerk.com", "clerk.dev", "clerk.accounts"], ["clerk"], [], 88),
    ("Firebase Auth", "Authentication", ["identitytoolkit.googleapis", "firebaseapp.com"], ["firebase"], [], 80),
    ("WorkOS", "Authentication", ["workos.com"], [], [], 82),
    ("Supabase Auth", "Authentication", ["supabase.co/auth"], [], [], 80),
    # Backend / data
    ("Supabase", "Database", ["supabase.co", "supabase.in"], ["supabase"], [], 86),
    ("Firebase", "Database", ["firebaseio.com", "firestore.googleapis"], ["firebase"], [], 82),
    ("Algolia", "Search", ["algolia.net", "algolianet"], ["algolia"], [], 86),
    ("Meilisearch", "Search", ["meilisearch"], [], [], 78),
    ("GraphQL", "API", [], ["/graphql", "graphql", "__typename", "apollo"], [], 80),
    ("Apollo", "API", ["apollographql"], ["apollo", "__apollo"], [], 82),
    # Realtime
    ("Pusher", "Realtime", ["pusher.com", "pusherapp"], ["pusher"], [], 84),
    ("Ably", "Realtime", ["ably.io"], ["ably"], [], 82),
    ("WebSocket", "Realtime", [], ["websocket", "socket.io", "new websocket"], [], 72),
    # Email / support / marketing
    ("Intercom", "Support", ["intercom.io", "intercomcdn"], ["intercom"], [], 86),
    ("Customer.io", "Email", ["customer.io"], [], [], 78),
    ("HubSpot", "Marketing", ["hubspot.com", "hs-scripts"], ["hubspot"], [], 82),
    ("Mailchimp", "Email", ["mailchimp.com", "list-manage"], [], [], 78),
    # Media / assets
    ("Cloudinary", "Storage", ["cloudinary.com"], ["cloudinary"], [], 82),
    ("imgix", "Storage", ["imgix.net"], [], [], 80),
    ("Contentful", "CMS", ["contentful.com"], ["contentful"], [], 80),
    ("Sanity", "CMS", ["sanity.io", "cdn.sanity"], ["sanity"], [], 80),
    # CMS / website builders — matched on hosts/paths/attributes, not brand words,
    # so customer logos or testimonials never trigger a false positive.
    ("WordPress", "CMS", [], ["/wp-content/", "/wp-includes/", "/wp-json/"], [("x-powered-by", "wordpress")], 90),
    ("WooCommerce", "Commerce", [], ["woocommerce-", "wc-ajax", "wc_add_to_cart"], [], 84),
    ("Webflow", "CMS", ["assets.website-files", "website-files.com"], ["wf-page", "data-wf-"], [("server", "webflow")], 88),
    ("Squarespace", "CMS", ["squarespace.com", "sqspcdn", "static1.squarespace"], [], [], 88),
    ("Wix", "CMS", ["wixstatic.com", "wixsite.com", "parastorage"], ["wix-warmup", "data-wix"], [("x-wix-request-id", "")], 88),
    ("Ghost", "CMS", ["ghost.io"], ["/ghost/api/"], [], 80),
    ("Drupal", "CMS", [], ["/sites/default/files", "drupal-settings-json"], [("x-generator", "drupal"), ("x-drupal-cache", "")], 86),
    ("Joomla", "CMS", [], ["/media/jui/", "option=com_content"], [], 80),
    ("HubSpot CMS", "CMS", ["hs-sites.com", "hubspotusercontent"], ["hs-scripts.com"], [], 82),
    ("Framer", "CMS", ["framerusercontent", "framer.app"], ["__framer", "data-framer-"], [], 86),
    ("Bubble", "CMS", ["bubble.io", "bubbleapps.io"], ["bubble_page", "/package/bubble"], [], 82),
    # Experimentation / feature flags
    ("LaunchDarkly", "Experimentation", ["launchdarkly.com", "ldcdn.us", "clientstream.launchdarkly"], ["launchdarkly", "ld-"], [], 88),
    ("Optimizely", "Experimentation", ["optimizely.com", "cdn.optimizely"], ["optimizely"], [], 86),
    ("Split", "Experimentation", ["split.io", "sdk.split"], ["splitio"], [], 84),
    ("Statsig", "Experimentation", ["statsig.com", "featureassets.org"], ["statsig"], [], 84),
    ("GrowthBook", "Experimentation", ["growthbook.io", "cdn.growthbook"], ["growthbook"], [], 82),
    ("VWO", "Experimentation", ["visualwebsiteoptimizer.com", "vwo.com"], ["_vwo", "vwo_"], [], 82),
    ("Google Optimize", "Experimentation", ["optimize.google.com"], ["google_optimize", "gaexp"], [], 78),
    ("Unleash", "Experimentation", ["getunleash.io", "unleash-hosted"], ["unleash"], [], 80),
    ("Flagsmith", "Experimentation", ["flagsmith.com"], ["flagsmith"], [], 80),
    # Commerce platforms
    ("Shopify", "Commerce", ["cdn.shopify.com", "myshopify.com", "shopifycdn"], ["/cdn/shop/", "shopify.loadfeatures"], [("x-shopify-stage", ""), ("x-shopid", "")], 92),
    ("Magento", "Commerce", [], ["/static/version", "mage/cookies", "mage-messages"], [("x-magento-", "")], 84),
    ("BigCommerce", "Commerce", ["bigcommerce.com", "mybigcommerce"], [], [], 84),
    ("Salesforce Commerce", "Commerce", ["demandware.net", "demandware.static"], ["/on/demandware.store"], [], 82),
    ("Snipcart", "Commerce", ["snipcart.com"], [], [], 80),
]


def detect(signals: Signals) -> list[Detection]:
    haystack = " ".join(signals.scripts + signals.html_markers + signals.generators).lower()
    hosts_joined = " ".join(signals.hosts).lower()
    headers_lower = {k.lower(): (v or "").lower() for k, v in signals.headers.items()}
    detections: list[Detection] = []

    for name, category, host_frags, markers, header_checks, base in _SIGNATURES:
        evidence: list[str] = []
        score = 0

        for frag in host_frags:
            hit = next((h for h in signals.hosts if frag in h.lower()), None)
            if hit:
                evidence.append(f"network host {hit}")
                score = max(score, base)
        for marker in markers:
            needle = marker.lower()
            if needle in haystack or needle in hosts_joined:
                evidence.append(f"page marker '{marker}'")
                score = max(score, base - 6)
        for key, value_frag in header_checks:
            if key in headers_lower and value_frag in headers_lower[key]:
                evidence.append(f"header {key}: {headers_lower[key][:40] or 'present'}")
                score = max(score, base)

        if evidence:
            # Multiple independent signals reinforce confidence, capped at 98.
            bonus = min(6, (len(evidence) - 1) * 3)
            detections.append(
                Detection(name=name, category=category, confidence=min(98, score + bonus), evidence=evidence[:4])
            )

    detections.sort(key=lambda d: d.confidence, reverse=True)
    return detections
