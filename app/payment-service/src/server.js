const crypto = require('crypto');
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const { pool, initializeDatabase, readinessCheck } = require('./db');
const {
  client,
  metricsMiddleware,
  paymentAuthorizeSuccessTotal,
  paymentAuthorizeFailureTotal,
  setFaultMetric,
  resetFaultMetrics,
  shutdownTracing
} = require('./observability');

const port = Number(process.env.PORT || 8080);
const faultState = { latencyMs: 0, errorRate: 0 };

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function faultMiddleware(req, res, next) {
  if (req.path.startsWith('/fault')) {
    return next();
  }
  Promise.resolve()
    .then(async () => {
      if (faultState.latencyMs > 0) {
        await sleep(faultState.latencyMs);
      }
      if (faultState.errorRate > 0 && Math.random() < faultState.errorRate) {
        const error = new Error('injected payment fault');
        error.statusCode = 503;
        throw error;
      }
    })
    .then(() => next())
    .catch(next);
}

function errorHandler(error, req, res, next) {
  if (res.headersSent) {
    return next(error);
  }
  console.error(JSON.stringify({ level: 'error', service: 'payment-service', message: error.message }));
  res.status(error.statusCode || 500).json({ error: error.publicMessage || error.message || 'internal_error' });
}

async function start() {
  await initializeDatabase();
  const app = express();
  app.disable('x-powered-by');
  app.use(helmet());
  app.use(cors());
  app.use(express.json({ limit: '64kb' }));
  app.use(metricsMiddleware);
  app.use(faultMiddleware);

  app.get('/health', (req, res) => res.json({ status: 'ok', service: 'payment-service' }));

  app.get('/ready', async (req, res, next) => {
    try {
      await readinessCheck();
      res.json({ status: 'ready' });
    } catch (error) {
      error.statusCode = 503;
      next(error);
    }
  });

  app.get('/metrics', async (req, res, next) => {
    try {
      res.set('content-type', client.register.contentType);
      res.end(await client.register.metrics());
    } catch (error) {
      next(error);
    }
  });

  app.post('/payment/authorize', async (req, res, next) => {
    try {
      const amountCents = Number(req.body.amountCents);
      if (!Number.isInteger(amountCents) || amountCents < 1) {
        paymentAuthorizeFailureTotal.inc();
        return res.status(400).json({ error: 'amountCents must be a positive integer' });
      }

      const authorizationId = `auth_${crypto.randomUUID()}`;
      const result = await pool.query(`
        INSERT INTO payments (authorization_id, amount_cents, status)
        VALUES ($1, $2, 'authorized')
        RETURNING authorization_id, amount_cents, status, created_at
      `, [authorizationId, amountCents]);

      paymentAuthorizeSuccessTotal.inc();
      res.status(201).json({
        authorizationId: result.rows[0].authorization_id,
        amountCents: result.rows[0].amount_cents,
        status: result.rows[0].status
      });
    } catch (error) {
      paymentAuthorizeFailureTotal.inc();
      next(error);
    }
  });

  app.post('/fault/latency', (req, res) => {
    const latencyMs = Math.max(0, Math.min(Number(req.body.latencyMs || 500), 5000));
    faultState.latencyMs = latencyMs;
    setFaultMetric('latency', latencyMs > 0);
    res.json({ status: 'latency_fault_updated', latencyMs });
  });

  app.post('/fault/error-rate', (req, res) => {
    const errorRate = Math.max(0, Math.min(Number(req.body.errorRate || 0.1), 1));
    faultState.errorRate = errorRate;
    setFaultMetric('error_rate', errorRate > 0);
    res.json({ status: 'error_rate_fault_updated', errorRate });
  });

  app.post('/fault/reset', (req, res) => {
    faultState.latencyMs = 0;
    faultState.errorRate = 0;
    resetFaultMetrics();
    res.json({ status: 'faults_reset' });
  });

  app.use((req, res) => res.status(404).json({ error: 'not_found' }));
  app.use(errorHandler);

  const server = app.listen(port, () => {
    console.log(JSON.stringify({ level: 'info', service: 'payment-service', message: 'server_started', port }));
  });

  async function shutdown(signal) {
    console.log(JSON.stringify({ level: 'info', service: 'payment-service', message: 'shutdown_started', signal }));
    server.close(async () => {
      await pool.end();
      await shutdownTracing();
      process.exit(0);
    });
  }

  process.on('SIGTERM', shutdown);
  process.on('SIGINT', shutdown);
}

start().catch((error) => {
  console.error(error);
  process.exit(1);
});
