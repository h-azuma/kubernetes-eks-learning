from prometheus_client import REGISTRY


def sample(name, **labels):
    return REGISTRY.get_sample_value(name, labels) or 0.0


def test_metrics_endpoint_uses_prometheus_text_format(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "workboard_http_requests_total" in response.text


def test_requests_are_counted_by_route_template(client):
    labels = dict(method="GET", route="/api/v1/tasks/{task_id}", status="404")
    before = sample("workboard_http_requests_total", **labels)
    duration_before = sample(
        "workboard_http_request_duration_seconds_count", method="GET", route="/api/v1/tasks/{task_id}"
    )
    for _ in range(2):
        client.get("/api/v1/tasks/00000000-0000-0000-0000-000000000000")
    assert sample("workboard_http_requests_total", **labels) == before + 2
    duration_after = sample(
        "workboard_http_request_duration_seconds_count", method="GET", route="/api/v1/tasks/{task_id}"
    )
    assert duration_after == duration_before + 2
    assert "00000000-0000" not in client.get("/metrics").text


def test_unknown_paths_share_one_label_and_metrics_is_not_measured(client):
    labels = dict(method="GET", route="unmatched", status="404")
    before = sample("workboard_http_requests_total", **labels)
    client.get("/no-such-path-1")
    client.get("/no-such-path-2")
    assert sample("workboard_http_requests_total", **labels) == before + 2
    client.get("/metrics")
    assert sample("workboard_http_requests_total", method="GET", route="/metrics", status="200") == 0
