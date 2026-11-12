"""The nginx gateway must send every API call the React app makes to the
service that actually owns the route. nginx picks the first matching regex
location, so this test replays that rule against the real config."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONF = (ROOT / "frontend" / "nginx.conf").read_text()

SERVICES = {
    "p03-company-service:9030": "company",
    "p03-student-service:9031": "student",
    "p03-job-service:9032": "job",
    "p03-application-service:9033": "application",
    "p03-event-service:9034": "event",
    "p03-assistant-service:9035": "assistant",
}


def routes():
    out = []
    for m in re.finditer(
        r"location ~ (\^\S+)\s*\{(.*?)\}", CONF, flags=re.S
    ):
        target = re.search(r"proxy_pass http://([^;]+);", m.group(2))
        out.append((re.compile(m.group(1)), SERVICES[target.group(1)]))
    return out


def owner(path):
    for pattern, service in routes():
        if pattern.search(path):
            return service
    return "spa"


@pytest.mark.parametrize(
    "path, expected",
    [
        # company side (axios, /api prefix)
        ("/api/companies/auth/login", "company"),
        ("/api/companies/me", "company"),
        ("/api/companies/students", "company"),
        ("/api/companies/applications/5/status", "company"),
        ("/api/companies/applications/5/resume", "company"),
        ("/api/companies/jobs/7/applicants", "company"),
        ("/api/companies/jobs", "job"),
        ("/api/companies/jobs/7", "job"),
        ("/api/companies/events", "event"),
        ("/api/companies/events/3/registrants", "event"),
        # student side (fetch, /gw prefix)
        ("/gw/auth/login", "student"),
        ("/gw/auth/me", "student"),
        ("/gw/jobs?keyword=data", "job"),
        ("/gw/jobs/7", "job"),
        ("/gw/jobs/7/applications", "application"),
        ("/gw/applications/me", "application"),
        ("/gw/applications/9/resume", "application"),
        ("/gw/events?city=x", "event"),
        ("/gw/events/3", "event"),
        ("/gw/events/3/registrations", "event"),
        ("/gw/registrations/me", "event"),
        ("/gw/assistant/chat", "assistant"),
        # SPA pages must NOT be proxied, or a browser refresh would break
        ("/jobs", "spa"),
        ("/jobs/7", "spa"),
        ("/events", "spa"),
        ("/applications", "spa"),
        ("/company/dashboard", "spa"),
    ],
)
def test_gateway_routes_each_call_to_its_owner(path, expected):
    assert owner(path) == expected


def test_prefix_is_stripped_before_forwarding():
    assert CONF.count("rewrite ^/gw(/.*)$ $1 break;") == 6


def test_dockerfile_builds_with_the_gateway_prefix():
    text = (ROOT / "frontend" / "Dockerfile").read_text()
    assert "ARG VITE_API_URL=/gw" in text
    assert "EXPOSE 9036" in text
