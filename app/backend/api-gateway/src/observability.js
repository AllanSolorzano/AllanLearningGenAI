const client = require('prom-client');
const { NodeSDK } = require('@opentelemetry/sdk-node');
const { OTLPTraceExporter } = require('@opentelemetry/exporter-trace-otlp-http');
const { resourceFromAttributes } = require('@opentelemetry/resources');
const { getNodeAutoInstrumentations } = require('@opentelemetry/auto-instrumentations-node');

const serviceName = process.env.OTEL_SERVICE_NAME || 'chaos-api-gateway';
const otlpEndpoint = process.env.OTEL_EXPORTER_OTLP_ENDPOINT;

client.collectDefaultMetrics({ prefix: 'chaos_api_gateway_' });

const httpRequestsTotal = new client.Counter({
  name: 'http_requests_total',
  help: 'Total HTTP requests handled by the service.',
  labelNames: ['method', 'route', 'status_code']
});

const httpRequestDurationSeconds = new client.Histogram({
  name: 'http_request_duration_seconds',
  help: 'HTTP request duration in seconds.',
  labelNames: ['method', 'route', 'status_code'],
  buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10]
});

const checkoutSuccessTotal = new client.Counter({
  name: 'checkout_success_total',
  help: 'Total successful checkout operations.'
});

const checkoutFailureTotal = new client.Counter({
  name: 'checkout_failure_total',
  help: 'Total failed checkout operations.',
  labelNames: ['stage']
});

const activeFaultMode = new client.Gauge({
  name: 'active_fault_mode',
  help: 'Active in-memory fault injection modes. 1 means enabled.',
  labelNames: ['mode']
});

let sdk;

function startTracing() {
  sdk = new NodeSDK({
    traceExporter: otlpEndpoint ? new OTLPTraceExporter() : undefined,
    resource: resourceFromAttributes({
      'service.name': serviceName,
      'service.namespace': 'ai-chaos-gameday',
      'deployment.environment.name': process.env.NODE_ENV || 'development'
    }),
    instrumentations: [
      getNodeAutoInstrumentations({
        '@opentelemetry/instrumentation-fs': { enabled: false }
      })
    ]
  });

  sdk.start();
}

async function shutdownTracing() {
  if (sdk) {
    await sdk.shutdown();
  }
}

function routeLabel(req) {
  return req.route && req.route.path ? `${req.baseUrl || ''}${req.route.path}` : req.path;
}

function metricsMiddleware(req, res, next) {
  const end = httpRequestDurationSeconds.startTimer({ method: req.method });

  res.on('finish', () => {
    const labels = {
      method: req.method,
      route: routeLabel(req),
      status_code: String(res.statusCode)
    };
    httpRequestsTotal.inc(labels);
    end(labels);
  });

  next();
}

function setFaultMetric(mode, enabled) {
  activeFaultMode.set({ mode }, enabled ? 1 : 0);
}

function resetFaultMetrics() {
  setFaultMetric('latency', false);
  setFaultMetric('error_rate', false);
}

resetFaultMetrics();
startTracing();

module.exports = {
  client,
  metricsMiddleware,
  checkoutSuccessTotal,
  checkoutFailureTotal,
  setFaultMetric,
  resetFaultMetrics,
  shutdownTracing
};
