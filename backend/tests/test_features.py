"""Feature inference reads the navigation link graph, not just fetched pages.

Without deep crawl an analysis fetches exactly one page, so page paths/titles alone
yielded zero features — which then cascaded into "Unable to determine" for entities,
flows, and permissions. The links on that page are observable evidence of the rest of
the product surface, so they are cited directly.
"""

from app.services.analyzer import AnalysisInputs, PageInfo, infer_features
from app.services.explorer import extract_link_paths, extract_visible_text

HOME = PageInfo(url="https://acme.com/", path="/", title="Acme", status=200)


def _inputs(link_paths: list[str], title: str = "Acme") -> AnalysisInputs:
    inputs = AnalysisInputs(product_name="Acme", host="acme.com", url="https://acme.com")
    inputs.pages.append(PageInfo(url="https://acme.com/", path="/", title=title, status=200))
    inputs.link_paths = link_paths
    return inputs


def test_features_inferred_from_navigation_of_a_single_page() -> None:
    features = infer_features(_inputs(["/login", "/pricing", "/docs", "/dashboard"]))
    names = {f["name"] for f in features}
    assert {"Authentication", "Billing & subscriptions", "Documentation", "Dashboard"} <= names


def test_feature_evidence_cites_the_specific_link() -> None:
    (auth,) = [f for f in infer_features(_inputs(["/login"])) if f["name"] == "Authentication"]
    assert any("/login" in e for e in auth["evidence"])
    assert auth["classification"] == "observed"


def test_no_navigation_evidence_yields_no_features() -> None:
    # A bare page with nothing observable must not invent a product surface.
    assert infer_features(_inputs([], title="")) == []


def test_keywords_do_not_match_inside_unrelated_words() -> None:
    # 'api' must not fire on "rapidly", 'search' must not fire on "researchers".
    features = infer_features(_inputs([], title="Rapidly built by researchers"))
    assert {f["name"] for f in features} == set()


def test_keyword_still_matches_word_prefixes() -> None:
    # Left-boundary matching must keep 'auth' → "authentication".
    names = {f["name"] for f in infer_features(_inputs(["/authentication"]))}
    assert "Authentication" in names


def test_features_are_detected_from_rendered_page_copy() -> None:
    inputs = _inputs([])
    inputs.pages[0].text = "Collaborate with your team in shared workspaces. Search projects and manage account settings."
    names = {feature["name"] for feature in infer_features(inputs)}
    assert {"Team collaboration", "Projects & workspaces", "Search", "Settings & configuration"} <= names


def test_blocked_page_copy_is_not_treated_as_product_evidence() -> None:
    inputs = _inputs([])
    inputs.pages[0].path = "/login"
    inputs.pages[0].title = "Account login"
    inputs.pages[0].status = 403
    inputs.pages[0].text = "account dashboard projects billing"
    assert infer_features(inputs) == []


def test_first_party_network_paths_support_feature_detection() -> None:
    inputs = _inputs([])
    inputs.network_signals = [{"host": "api.acme.com", "path": "/api/notifications"}]
    names = {feature["name"] for feature in infer_features(inputs)}
    assert {"Developer API", "Notifications"} <= names


def test_visible_text_excludes_script_and_style_content() -> None:
    html = "<style>.billing{color:red}</style><script>openDashboard()</script><main>Team collaboration</main>"
    text = extract_visible_text(html)
    assert text == "Team collaboration"


class TestLinkExtraction:
    def test_keeps_same_host_paths_only(self) -> None:
        html = """
          <a href="/pricing">Pricing</a>
          <a href="https://acme.com/docs">Docs</a>
          <a href="https://twitter.com/acme">Twitter</a>
          <a href="mailto:hi@acme.com">Mail</a>
          <a href="#top">Top</a>
        """
        assert extract_link_paths(html, "https://acme.com/", "acme.com") == ["/pricing", "/docs"]

    def test_deduplicates_and_ignores_query_and_fragment(self) -> None:
        html = '<a href="/docs?x=1">a</a><a href="/docs#intro">b</a><a href="/docs">c</a>'
        assert extract_link_paths(html, "https://acme.com/", "acme.com") == ["/docs"]
