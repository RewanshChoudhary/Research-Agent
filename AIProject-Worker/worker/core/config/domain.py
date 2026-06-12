from worker.enums import Domain
DOMAIN_CONFIGS = {
    Domain.GENERAL: {
        "system_prompt": "You are a helpful research assistant. Provide balanced, well-sourced information.",
        "search_prefix": "",
        "trusted_sources": [],
        "excluded_sources": [],
        "fact_check_threshold": 0.70,
        "cache_ttl_hours": 24,
    },
    Domain.MEDICAL: {
        "system_prompt": "You are a medical research assistant. Prioritize peer-reviewed studies and official health sources. Note when evidence is preliminary.",
        "search_prefix": "clinical study peer reviewed",
        "trusted_sources": ["pubmed.ncbi.nlm.nih.gov", "who.int", "cdc.gov", "nih.gov"],
        "excluded_sources": ["reddit.com", "quora.com", "medium.com"],
        "fact_check_threshold": 0.85,
        "cache_ttl_hours": 72,
    },
    Domain.LEGAL: {
        "system_prompt": "You are a legal research assistant. Reference statutes, case law, and official legal sources. Note jurisdictions clearly.",
        "search_prefix": "legal",
        "trusted_sources": ["congress.gov", "law.cornell.edu", "supremecourt.gov"],
        "excluded_sources": ["reddit.com", "quora.com"],
        "fact_check_threshold": 0.85,
        "cache_ttl_hours": 72,
    },
    Domain.TECHNICAL: {
        "system_prompt": "You are a technical research assistant. Focus on official documentation, specifications, and reputable technical publications. Prioritize accuracy and cite specific versions or implementations where applicable.",
        "search_prefix": "technical documentation",
        "trusted_sources": ["docs.github.com", "learn.microsoft.com", "developer.mozilla.org", "kubernetes.io", "aws.amazon.com"],
        "excluded_sources": ["reddit.com", "quora.com", "medium.com"],
        "fact_check_threshold": 0.75,
        "cache_ttl_hours": 48,
    },
    Domain.OTHER: {
        "system_prompt": "You are a helpful research assistant. Provide balanced, well-sourced information.",
        "search_prefix": "",
        "trusted_sources": [],
        "excluded_sources": [],
        "fact_check_threshold": 0.70,
        "cache_ttl_hours": 24,
    },
}
def resolve_config(domain: Domain) -> dict:
    return DOMAIN_CONFIGS.get(domain, DOMAIN_CONFIGS[Domain.GENERAL])

