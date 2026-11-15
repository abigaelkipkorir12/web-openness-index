from pathlib import Path
import argparse
import pandas as pd


IMPORTANT_SIGNALS = {
    # Browser
    "browser.navigation",
    "browser.network_summary",
    "browser.rendered_document",

    # Crawler
    "crawler.browser_http_difference",
    "crawler.crawl_delays",
    "crawler.homepage_policy_allowed",
    "crawler.robots_exists",
    "crawler.robots_status",
    "crawler.sitemaps",
    "crawler.user_agents",

    # Economic
    "economic.registration_required",
    "economic.subscription_required",

    # Human
    "human.authentication_challenge",
    "human.browser_captcha_marker_visible",
    "human.browser_cookie_wall_marker_visible",
    "human.browser_login_marker_visible",
    "human.browser_paywall_marker_visible",
    "human.captcha_detected",
    "human.cookie_wall_detected",
    "human.homepage_accessible",
    "human.javascript_required",
    "human.login_required",
    "human.paywall_detected",
    "human.rate_limited",

    # Infrastructure
    "infrastructure.acceleration_hints",
    "infrastructure.bot_management_hints",
    "infrastructure.cache_headers",
    "infrastructure.cache_status",
    "infrastructure.cdn",
    "infrastructure.challenge_response",
    "infrastructure.dns_provider",
    "infrastructure.edge_location_hints",
    "infrastructure.edge_provider",
    "infrastructure.edge_response_hints",
    "infrastructure.hosting_provider",
    "infrastructure.load_balancer_hints",
    "infrastructure.response_cookie_fingerprints",
    "infrastructure.waf",

    # Legal
    "legal.ai_restrictions",
    "legal.license",
    "legal.license_links",
    "legal.policy_links",
    "legal.scraping_restrictions",

    # Metadata
    "metadata.json_ld",
    "metadata.llms_txt_exists",

    # Network
    "network.dns_address_count",
    "network.dns_addresses",
    "network.dns_addresses_truncated",
    "network.dns_canonical_name",
    "network.dns_nameservers",
    "network.dns_resolved",
    "network.http_version",
    "network.tls_version",

    # Preservation
    "preservation.archive_blocked",
    "preservation.archive_coverage",
    "preservation.cache_behavior",
    "preservation.cache_header_hints",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a CSV containing only the important Web Openness signals."
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Path to signal_similarity.csv",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("important_signal_results.csv"),
        help="Output CSV path",
    )

    args = parser.parse_args()

    df = pd.read_csv(args.input)

    important = df[df["signal"].isin(IMPORTANT_SIGNALS)].copy()

    important["group"] = important["signal"].str.split(".").str[0]

    important["observed_rate"] = (
        important["observed_count"]
        / (
            important["observed_count"]
            + important["no_evidence_count"]
            + important["skipped_count"]
            + important["error_count"]
        )
        * 100
    ).round(1)

    important["similarity_percent"] = (
        important["similarity_score"] * 100
    ).round(1)

    columns = [
        "group",
        "signal",
        "domain_count",
        "observed_count",
        "no_evidence_count",
        "skipped_count",
        "error_count",
        "observed_rate",
        "unique_values",
        "similarity_percent",
        "most_common_value",
    ]

    important = important[columns].sort_values(
        by=["group", "signal"]
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    important.to_csv(args.output, index=False)

    print(f"Wrote {len(important)} important signals to:")
    print(args.output)


if __name__ == "__main__":
    main()