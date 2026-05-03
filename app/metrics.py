from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

# Ticket metrics
ticket_created_counter = Counter(
    'ticketpilot_tickets_created_total',
    'Total number of tickets created'
)

ticket_resolved_counter = Counter(
    'ticketpilot_tickets_resolved_total',
    'Total number of tickets resolved'
)

ticket_escalated_counter = Counter(
    'ticketpilot_tickets_escalated_total',
    'Total number of tickets escalated'
)

# Token metrics
token_usage_counter = Counter(
    'ticketpilot_token_usage_total',
    'Total tokens used by LLM calls',
    ['model']
)

# Latency metrics
ticket_processing_seconds = Histogram(
    'ticketpilot_ticket_processing_seconds',
    'Time spent processing tickets',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

# Worker metrics
worker_processed_counter = Counter(
    'ticketpilot_worker_tickets_processed_total',
    'Total tickets processed by worker'
)

# HTTP request metrics
http_request_duration_seconds = Histogram(
    'ticketpilot_http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint', 'status']
)

def metrics_endpoint():
    """Return Prometheus metrics."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
