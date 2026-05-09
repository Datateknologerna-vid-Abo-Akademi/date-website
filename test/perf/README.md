# Event performance test

This directory contains k6 scripts for local event signup load testing.

## Setup

Create or choose an event that:

- has the slug `perftest`, or pass another slug with `EVENT_SLUG`
- has signup enabled
- is open for non-members
- does not require captcha or passcode

## Run

Start the local stack, then run:

```bash
docker run --rm -i grafana/k6:latest run - < test/perf/test-event.js
```

Useful overrides:

```bash
docker run --rm -i \
  grafana/k6:latest run \
  -e BASE_URL=http://host.docker.internal:8000 \
  -e EVENT_SLUG=perftest \
  -e TARGET_VUS=100 \
  -e RAMP_DURATION=30s \
  - < test/perf/test-event.js
```

When running k6 directly on the host instead of inside Docker, `BASE_URL` can usually stay as `http://localhost:8000`.
