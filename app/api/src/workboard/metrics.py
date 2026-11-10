import time

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

METRICS_PATH = "/metrics"
UNMATCHED_ROUTE = "unmatched"

REQUESTS_TOTAL = Counter(
    "workboard_http_requests_total",
    "HTTP リクエスト数",
    ["method", "route", "status"],
)
REQUEST_DURATION_SECONDS = Histogram(
    "workboard_http_request_duration_seconds",
    "HTTP リクエストの処理時間（秒）",
    ["method", "route"],
)


def route_template(request: Request) -> str:
    """ラベル数を抑えるため、実パスではなくパステンプレートを使う。"""
    route = request.scope.get("route")
    return route.path if route is not None else UNMATCHED_ROUTE


async def record_metrics(request: Request, call_next):
    if request.url.path == METRICS_PATH:
        return await call_next(request)
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = route_template(request)
        REQUESTS_TOTAL.labels(request.method, route, str(status)).inc()
        REQUEST_DURATION_SECONDS.labels(request.method, route).observe(time.perf_counter() - started)


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
