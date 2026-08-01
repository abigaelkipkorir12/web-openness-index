from web_openness.probes.robots import parse_robots


def test_parse_robots_extracts_agents_delays_and_sitemaps() -> None:
    parsed = parse_robots(
        """
        User-agent: *
        Crawl-delay: 2
        Allow: /

        User-agent: GPTBot
        User-agent: Google-Extended
        Disallow: /

        Sitemap: https://example.org/sitemap.xml
        """
    )

    assert parsed.user_agents == ("*", "google-extended", "gptbot")
    assert parsed.ai_user_agents == ("google-extended", "gptbot")
    assert parsed.crawl_delays == {"*": "2"}
    assert parsed.sitemaps == ("https://example.org/sitemap.xml",)
