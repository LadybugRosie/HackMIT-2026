from prometheus_client import Counter, Histogram

REQUESTS_TOTAL = Counter(
    "requests_total",
    "Total number of requests",
    ["endpoint", "method"],
)
REQUESTS_FAILED_TOTAL = Counter(
    "requests_failed_total",
    "Total number of failed requests",
    ["endpoint", "method", "reason"],
)
CACHE_HITS_TOTAL = Counter(
    "cache_hits_total",
    "Total cache hits",
)
CACHE_MISSES_TOTAL = Counter(
    "cache_misses_total",
    "Total cache misses",
)
JOBS_QUEUED_TOTAL = Counter(
    "jobs_queued_total",
    "Total jobs queued",
)
REQUEST_LATENCY_SECONDS = Histogram(
    "request_latency_seconds",
    "Request latency in seconds",
    ["endpoint", "method"],
)
