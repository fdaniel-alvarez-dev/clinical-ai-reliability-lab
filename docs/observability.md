# Observability

This repo treats observability as a first-class feature.

## Logging

- Structured JSON logs via `structlog`
- Intended use: feed logs into your preferred local stack (or just read them in stdout)

## Tracing (OpenTelemetry)

FastAPI is instrumented via `opentelemetry-instrumentation-fastapi`.

Workflow spans include:
- `normalize`
- `biomarker_graph`
- `draft`
- `validate`
- `evaluate`
- `export`

Requests:
- `X-Correlation-Id` is accepted and echoed back in the response.
- The correlation id is attached to request spans as `correlation_id`.

## OTLP export (optional)

Set:

- `OTEL_EXPORTER_OTLP_ENDPOINT` (e.g., `http://localhost:4317`)
- `OTEL_EXPORTER_OTLP_INSECURE=true`

If the endpoint is not configured, traces are exported to stdout via `ConsoleSpanExporter` for local inspection.

## SigNoz (optional)

This repo includes a docker-compose profile for a local SigNoz UI plus an OTLP gateway collector.

Start:

```bash
docker compose --profile observability up -d
```

Configure the API to export traces to the local collector:

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_EXPORTER_OTLP_INSECURE=true
```

Open SigNoz at `http://localhost:3301`.
