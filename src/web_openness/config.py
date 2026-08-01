from dataclasses import dataclass

DEFAULT_USER_AGENT = (
    "WebOpennessObservatory/0.1 "
    "(+https://github.com/shayne-longpre/web-openness-index; research collector)"
)


@dataclass(frozen=True, slots=True)
class ScanConfig:
    """Explicit network and evidence limits for one domain scan."""

    user_agent: str = DEFAULT_USER_AGENT
    request_budget: int = 8
    request_delay_seconds: float = 1.0
    timeout_seconds: float = 15.0
    max_response_bytes: int = 1_000_000
    max_redirects: int = 5

    def __post_init__(self) -> None:
        if not self.user_agent.strip():
            raise ValueError("user_agent must not be empty")
        if self.request_budget < 1:
            raise ValueError("request_budget must be at least 1")
        if self.request_delay_seconds < 0:
            raise ValueError("request_delay_seconds must not be negative")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_response_bytes < 1:
            raise ValueError("max_response_bytes must be at least 1")
        if self.max_redirects < 0:
            raise ValueError("max_redirects must not be negative")

    @property
    def user_agent_token(self) -> str:
        """Return the product token used for robots.txt matching."""

        return self.user_agent.split("/", maxsplit=1)[0].strip()
