const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const { pool, initializeDatabase, readinessCheck, withTransaction } = require('./db');
const {
  client,
  metricsMiddleware,
  orderCreatedTotal,
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
        const error = new Error('injected order fault');
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
  console.error(JSON.stringify({ level: 'error', service: 'order-service', message: error.message }));
  res.status(error.statusCode || 500).json({ error: error.publicMessage || error.message || 'internal_error' });
}

function validateItems(items) {
  if (!Array.isArray(items) || items.length === 0) {
    const error = new Error('items are required');
    error.statusCode = 400;
    throw error;
  }

  for (const item of items) {
    if (!Number.isInteger(Number(item.productId)) || Number(item.productId) < 1) {
      const error = new Error('invalid productId');
      error.statusCode = 400;
      throw error;
    }
    if (!Number.isInteger(Number(item.quantity)) || Number(item.quantity) < 1) {
      const error = new Error('invalid quantity');
      error.statusCode = 400;
      throw error;
    }
    if (!Number.isInteger(Number(item.priceCents)) || Number(item.priceCents) < 1) {
      const error = new Error('invalid priceCents');
      error.statusCode = 400;
      throw error;
    }
  }
}

async function createOrder(items, payment = {}) {
  validateItems(items);
  return withTransaction(async (clientConnection) => {
    const totalCents = items.reduce((sum, item) => sum + Number(item.priceCents) * Number(item.quantity), 0);
    const orderResult = await clientConnection.query(`
      INSERT INTO orders (status, total_cents, payment_authorization_id, payment_status)
      VALUES ($1, $2, $3, $4)
      RETURNING id, status, total_cents, payment_authorization_id, payment_status, created_at
    `, [
      payment.status === 'fallback' ? 'payment_pending' : 'paid',
      totalCents,
      payment.authorizationId || null,
      payment.status || null
    ]);

    const order = orderResult.rows[0];
    for (const item of items) {
      await clientConnection.query(`
        INSERT INTO order_items (order_id, product_id, quantity, price_cents)
        VALUES ($1, $2, $3, $4)
      `, [order.id, item.productId, item.quantity, item.priceCents]);
    }

    orderCreatedTotal.inc();
    return order;
  });
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

  app.get('/health', (req, res) => res.json({ status: 'ok', service: 'order-service' }));

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

  app.get('/orders', async (req, res, next) => {
    try {
      const result = await pool.query(`
        SELECT id, status, total_cents, payment_authorization_id, payment_status, created_at
        FROM orders
        ORDER BY created_at DESC
        LIMIT 25
      `);
      res.json({ orders: result.rows });
    } catch (error) {
      next(error);
    }
  });

  app.post('/orders', async (req, res, next) => {
    try {
      const order = await createOrder(req.body.items, req.body.payment);
      res.status(201).json({ order });
    } catch (error) {
      next(error);
    }
  });

  app.get('/orders/:id', async (req, res, next) => {
    try {
      const result = await pool.query(`
        SELECT id, status, total_cents, payment_authorization_id, payment_status, created_at
        FROM orders
        WHERE id = $1
      `, [Number(req.params.id)]);
      if (result.rowCount === 0) {
        return res.status(404).json({ error: 'order not found' });
      }
      const items = await pool.query(`
        SELECT product_id, quantity, price_cents
        FROM order_items
        WHERE order_id = $1
        ORDER BY product_id ASC
      `, [Number(req.params.id)]);
      res.json({ order: result.rows[0], items: items.rows });
    } catch (error) {
      next(error);
    }
  });

  app.post('/checkout', async (req, res, next) => {
    try {
      const order = await createOrder(req.body.items, req.body.payment);
      res.status(201).json({ order });
    } catch (error) {
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
    console.log(JSON.stringify({ level: 'info', service: 'order-service', message: 'server_started', port }));
  });

  async function shutdown(signal) {
    console.log(JSON.stringify({ level: 'info', service: 'order-service', message: 'shutdown_started', signal }));
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
