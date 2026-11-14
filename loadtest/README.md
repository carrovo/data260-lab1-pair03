# JMeter load test (Pair 03)

`handshake.jmx` runs four scenarios at the same time, each with its own virtual users:

1. Student login, then job search (keyword, city) and job detail (Student 9031, Job 9032)
2. Student login, then submit an application with a PDF resume (Application 9033)
3. Student login, then event search and event registration (Event 9034)
4. Company login, then the company's jobs and events (Company 9030, Job 9032, Event 9034)

Virtual users log in as the 200 seeded students (`seed3.student.001` to `200`), so load the
demo data first (`docker compose --env-file .env.compose --profile seed run --rm p03-seed`).
`resume.pdf` must stay next to the plan file; run JMeter from this folder.

## Run (non-GUI, no real secrets in any file)

Each virtual user logs in once and then repeats its scenario `loops` times. Ramp up quickly and
use enough loops that all users are active at the same time (watch `Active:` in the output):

    cd loadtest
    jmeter -n -t handshake.jmx -Jusers=25  -Jrampup=20 -Jloops=30 -l results_100.jtl -e -o report_100
    jmeter -n -t handshake.jmx -Jusers=75  -Jrampup=30 -Jloops=30 -l results_300.jtl -e -o report_300
    jmeter -n -t handshake.jmx -Jusers=125 -Jrampup=30 -Jloops=30 -l results_500.jtl -e -o report_500

`users` is per scenario, so 25 means 100 concurrent users in total (four scenarios). Use a new
`-l` file and a new `-o` folder each time (JMeter appends to an old `.jtl`). Other properties:
`host`, `*_port` (default 9030 to 9034), `think_ms` (default 500), `password`.
For Kubernetes use a load balancer address as `-Jhost`; `kubectl port-forward` cannot carry this load.

## Expected status codes

Applying twice to the same job or registering twice is a business rule (409), and seed data
overlaps with the random picks, so the plan accepts 201 and 409 there, and 404 for events
that are already in the past. Anything else is counted as an error.

## What to record for the report

From the HTML report: average, p95 and p99 response time, throughput (requests/s) and error %
per sampler, for 100, 300 and 500 users. Put the numbers in `METRICS.md`.

`build_plan.py` regenerates `handshake.jmx`. The plan has not been run yet: only checked as
valid XML, so run it once with 5 users and read the first result file before the big runs.
