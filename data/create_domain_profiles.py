

import argparse
import json
from pathlib import Path

import pandas as pd

IMPORTANT_SIGNALS = {

    # Public and crawler
    "browser_http_difference": "crawler.browser_http_difference",
    "crawl_delays": "crawler.crawl_delays",
    "robots_allowed": "crawler.homepage_policy_allowed",
    "robots_exists": "crawler.robots_exists",
    "robots_status": "crawler.robots_status",
    "sitemaps": "crawler.sitemaps",
    "user_agents": "crawler.user_agents",

    # Human
    "authentication_challenge": "human.authentication_challenge",
    "browser_captcha": "human.browser_captcha_marker_visible",
    "browser_cookie_wall": "human.browser_cookie_wall_marker_visible",
    "browser_login": "human.browser_login_marker_visible",
    "browser_paywall": "human.browser_paywall_marker_visible",
    "captcha": "human.captcha_detected",
    "cookie_wall": "human.cookie_wall_detected",
    "homepage_accessible": "human.homepage_accessible",
    "http_access": "human.http_access_disposition",
    "javascript_required": "human.javascript_required",
    "login_required": "human.login_required",
    "paywall": "human.paywall_detected",
    "rate_limited": "human.rate_limited",

    # Additional evidence
    "browser_navigation": "browser.navigation",
    "browser_network_summary": "browser.network_summary",
    "browser_rendered_document": "browser.rendered_document",

    # DNS and network reachability
    "dns_address_count": "network.dns_address_count",
    "dns_addresses": "network.dns_addresses",
    "dns_addresses_truncated": "network.dns_addresses_truncated",
    "dns_nameservers": "network.dns_nameservers",
    "dns_resolved": "network.dns_resolved",

    # TLS and HTTP connection
    "http_version": "network.http_version",
    "tls_certificate_issuer": "network.tls_certificate_issuer",
    "tls_version": "network.tls_version",

    # Delivery and protection infrastructure
    "acceleration": "infrastructure.acceleration_hints",
    "bot_management": "infrastructure.bot_management_hints",
    "cache_headers": "infrastructure.cache_headers",
    "cache_status": "infrastructure.cache_status",
    "cdn": "infrastructure.cdn",
    "challenge": "infrastructure.challenge_response",
    "dns_provider": "infrastructure.dns_provider",
    "edge_location": "infrastructure.edge_location_hints",
    "edge_provider": "infrastructure.edge_provider",
    "edge_response": "infrastructure.edge_response_hints",
    "hosting_provider": "infrastructure.hosting_provider",
    "load_balancer": "infrastructure.load_balancer_hints",
    "response_cookies": "infrastructure.response_cookie_fingerprints",
    "waf": "infrastructure.waf",

    # Machine-interface access
    "api_documentation": "agent.api_documentation",
    "openapi": "agent.openapi",
    "graphql": "agent.graphql",
    "agent_card": "agent.agent_card",
    "interface_links": "agent.interface_links",
    "mcp": "agent.mcp",
    "oauth_metadata": "agent.oauth_metadata",
    "a2a": "agent.a2a",
    "llms_txt": "metadata.llms_txt_exists",

    # Legal and policy restrictions
    "ai_restrictions": "legal.ai_restrictions",
    "license": "legal.license",
    "license_links": "legal.license_links",
    "policy_links": "legal.policy_links",
    "scraping_restrictions": "legal.scraping_restrictions",

    # Economic access
    "registration_required": "economic.registration_required",
    "subscription_required": "economic.subscription_required",

    # Preservation and caching
    "archive_blocked": "preservation.archive_blocked",
    "archive_coverage": "preservation.archive_coverage",
    "cache_behavior": "preservation.cache_behavior",
    "cache_header_hints": "preservation.cache_header_hints",
}


# Create profile labels
TECHNICAL_SIGNALS = [
    "cdn",
    "waf",
    "bot_management",
    "challenge",
    "response_cookies",
    "load_balancer",
    "rate_limited",
    "captcha",
]


def parse_value(value_json):
    """
    Convert the value_json text into a Python value.
    """
    if pd.isna(value_json):
        return None

    try:
        return json.loads(value_json)
    except (TypeError, json.JSONDecodeError):
        return str(value_json)


def display_value(value_json, outcome):
    """
    Create a readable value for the output file.

    Unkown if skipped or no evidence
    """
    if outcome != "observed":
        return "Unknown"

    value = parse_value(value_json)

    if value is None:
        return "Unknown"

    if value is True:
        return "Yes"

    if value is False:
        return "No"

    if isinstance(value, list):
        if not value:
            return "No"
        return json.dumps(value, sort_keys=True)

    if isinstance(value, dict):
        if not value:
            return "No"
        return json.dumps(value, sort_keys=True)

    return str(value)


def find_signal_row(domain_rows, signal):
    """
    Find one signal's row for a specific domain.

    The duplicate-removal step ensures that there should be at most
    one current row for each domain/signal pair.
    """
    matches = domain_rows[domain_rows["signal"] == signal]

    if matches.empty:
        return None

    return matches.iloc[0]


def get_signal_outcome(domain_rows, signal):
    """
    Return the scanner outcome for one signal.

    Examples:
        observed
        no_evidence
        skipped
        error
        not_recorded
    """
    row = find_signal_row(domain_rows, signal)

    if row is None:
        return "not_recorded"

    return row["outcome"]


def get_signal_value(domain_rows, signal):
    """
    Return a readable value and outcome for one signal.
    """
    row = find_signal_row(domain_rows, signal)

    if row is None:
        return "Unknown", "not_recorded"

    outcome = row["outcome"]
    value = display_value(row["value_json"], outcome)

    return value, outcome


def signal_found(domain_rows, signal):
    """
    Determine whether a signal found positive evidence.

    This function handles booleans, lists, and dictionaries.
    For example, ["cloudflare"] counts as evidence being found.
    """
    row = find_signal_row(domain_rows, signal)

    if row is None or row["outcome"] != "observed":
        return False

    value = parse_value(row["value_json"])

    if value is None or value is False:
        return False

    if isinstance(value, (list, dict)):
        return bool(value)

    return True


def all_observed_negative(domain_rows, signal_names):
    """
    Check whether all selected signals were observed and negative.

    A skipped, errored, or no_evidence signal does not count as negative.
    This prevents incomplete scans from being treated as clean results.
    """
    for short_name in signal_names:
        signal = IMPORTANT_SIGNALS[short_name]
        row = find_signal_row(domain_rows, signal)

        if row is None or row["outcome"] != "observed":
            return False

        value = parse_value(row["value_json"])

        if value not in (False, None, [], {}):
            return False

    return True


def classify_profile(domain_rows):
    """
    Give each domain a broad access profile.

    These labels summarize observed patterns. They do not claim that
    a website is secure or insecure.
    """
    outcomes = [
        get_signal_outcome(domain_rows, signal)
        for signal in IMPORTANT_SIGNALS.values()
    ]

    # If none of the important signals produced usable evidence,
    # the domain cannot be meaningfully classified.
    if all(
        outcome in {"skipped", "error", "no_evidence", "not_recorded"}
        for outcome in outcomes
    ):
        return "inconclusive"

    has_robots = signal_found(
        domain_rows,
        IMPORTANT_SIGNALS["robots_exists"],
    )

    has_policy = (
        signal_found(
            domain_rows,
            IMPORTANT_SIGNALS["scraping_restrictions"],
        )
        or signal_found(
            domain_rows,
            IMPORTANT_SIGNALS["ai_restrictions"],
        )
    )

    has_technical_protection = any(
        signal_found(
            domain_rows,
            IMPORTANT_SIGNALS[name],
        )
        for name in TECHNICAL_SIGNALS
    )

    if has_policy and has_technical_protection:
        return "policy_and_technical_protection"

    if has_technical_protection and has_robots:
        return "layered_protection"

    if has_technical_protection:
        return "technical_protection_only"

    if has_policy:
        return "policy_only"

    if has_robots:
        return "robots_only"

    return "minimal_observed_protection"


def identify_flags(domain_rows):
    """
    Identify domain patterns that deserve manual review.

    These flags do not prove that something is wrong. They simply
    identify interesting combinations in the observations.
    """
    flags = []

    robots_signal = IMPORTANT_SIGNALS["robots_exists"]
    robots_outcome = get_signal_outcome(domain_rows, robots_signal)
    robots_found = signal_found(domain_rows, robots_signal)

    technical_found = any(
        signal_found(
            domain_rows,
            IMPORTANT_SIGNALS[name],
        )
        for name in TECHNICAL_SIGNALS
    )

    # A site has technical protection but no observed robots.txt.
    if (
        robots_outcome == "observed"
        and not robots_found
        and technical_found
    ):
        flags.append("technical_protection_without_robots")

    # A site has robots.txt, but all selected technical protections
    # were explicitly observed as negative.
    if robots_found and all_observed_negative(
        domain_rows,
        TECHNICAL_SIGNALS,
    ):
        flags.append("robots_only")

    # These flags show that the scan did not fully evaluate the domain.
    outcomes = [
        get_signal_outcome(domain_rows, signal)
        for signal in IMPORTANT_SIGNALS.values()
    ]

    if "skipped" in outcomes:
        flags.append("contains_skipped_signals")

    if "error" in outcomes:
        flags.append("contains_errors")

    if "no_evidence" in outcomes:
        flags.append("contains_no_evidence")

    if not flags:
        return "none"

    return "; ".join(flags)


def create_profiles(input_path, output_path):
    """
    Read observations.csv and create the profile files.
    """
    # Load the scanner's observation table.
    observations = pd.read_csv(input_path)

    # Convert timestamps so that the newest observation can be selected.
    observations["completed_at"] = pd.to_datetime(
        observations["completed_at"],
        errors="coerce",
    )

    # Newest observations appear first.
    observations = observations.sort_values(
        "completed_at",
        ascending=False,
    )

    # Keep only the newest result for each domain/signal pair.
    observations = observations.drop_duplicates(
        subset=["domain", "signal"],
        keep="first",
    )

    profile_rows = []
    review_rows = []

    # Process each domain separately.
    for domain, domain_rows in observations.groupby("domain"):
        profile = {"domain": domain}

        # Add a value and outcome column for every relevant signal.
        for short_name, signal in IMPORTANT_SIGNALS.items():
            value, outcome = get_signal_value(
                domain_rows,
                signal,
            )

            profile[f"{short_name}_value"] = value
            profile[f"{short_name}_outcome"] = outcome

        # Add a summary label and manual-review flags.
        profile["protection_profile"] = classify_profile(domain_rows)
        profile["review_flags"] = identify_flags(domain_rows)

        # Count the different scanner outcomes for this domain.
        profile["observed_count"] = int(
            (domain_rows["outcome"] == "observed").sum()
        )
        profile["no_evidence_count"] = int(
            (domain_rows["outcome"] == "no_evidence").sum()
        )
        profile["skipped_count"] = int(
            (domain_rows["outcome"] == "skipped").sum()
        )
        profile["error_count"] = int(
            (domain_rows["outcome"] == "error").sum()
        )

        profile_rows.append(profile)

        # Put only flagged domains into the smaller review file.
        if profile["review_flags"] != "none":
            review_rows.append(
                {
                    "domain": domain,
                    "protection_profile": profile[
                        "protection_profile"
                    ],
                    "review_flags": profile["review_flags"],
                }
            )

    # Convert the collected profiles into a table.
    profiles = pd.DataFrame(profile_rows)

    # Make sure the output directory exists.
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Write the complete domain profile.
    profiles.to_csv(
        output_path,
        index=False,
    )

    # Write the smaller manual-review queue.
    review_path = output_path.with_name(
        "manual_review_queue.csv"
    )

    pd.DataFrame(review_rows).to_csv(
        review_path,
        index=False,
    )

    print(f"Wrote domain profiles to: {output_path}")
    print(f"Wrote manual review queue to: {review_path}")
    print(f"Domains processed: {len(profiles)}")


def main():
    """
    Read the input and output paths from the command line.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Create domain profiles from observations.csv."
        )
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Path to observations.csv",
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path for the domain profile CSV",
    )

    args = parser.parse_args()

    create_profiles(
        args.input,
        args.output,
    )


if __name__ == "__main__":
    main()