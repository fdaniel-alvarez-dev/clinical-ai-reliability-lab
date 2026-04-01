# Observability

This repo treats observability as a first-class feature.

## Logging

- Structured JSON logs via `structlog`
- Intended use: feed logs into your preferred local stack (or just read them in stdout)

## Tracing (OpenTelemetry)

FastAPI is instrumented via `opentelemetry-instrumentation-fastapi`.

Workflow spans include:
- `normalize`
- `draft`
- `validate`
- `evaluate`
- `export`

## OTLP export (optional)

Set:

- `OTEL_EXPORTER_OTLP_ENDPOINT` (e.g., `http://localhost:4317`)
- `OTEL_EXPORTER_OTLP_INSECURE=true`

If the endpoint is not configured, traces are exported to stdout via `ConsoleSpanExporter` for local inspection.

## SigNoz (optional)

This repo includes a minimal docker-compose profile placeholder for a local observability stack.

Trade-off: SigNoz is powerful but adds operational weight. The default posture keeps the repo runnable without it.

