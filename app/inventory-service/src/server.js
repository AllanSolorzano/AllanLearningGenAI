const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const { pool, initializeDatabase, readinessCheck } = require('./db');
const {
  client,
  metricsMiddleware,
  inventoryReserveSuccessTotal,
  inventoryReserveFailureTotal,
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
        const error = new Error('injected inventory fault');
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
  console.error(JSON.stringify({ level: 'error', service: 'inventory-service', message: error.message }));
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

  app.get('/health', (req, res) => res.json({ status: 'ok', service: 'inventory-service' }));

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

  app.get('/products', async (req, res, next) => {
    try {
      const result = await pool.query(`
        SELECT p.id, p.name, p.description, p.price_cents, i.quantity AS inventory
        FROM products p
        JOIN inventory i ON i.product_id = p.id
        ORDER BY p.id ASC
      `);
      res.json({ products: result.rows });
    } catch (error) {
      next(error);
    }
  });

  app.get('/inventory/:productId', async (req, res, next) => {
    try {
      const productId = Number(req.params.productId);
      const result = await pool.query(`
        SELECT p.id AS product_id, p.name, p.price_cents, i.quantity
        FROM products p
        JOIN inventory i ON i.product_id = p.id
        WHERE p.id = $1
      `, [productId]);
      if (result.rowCount === 0) {
        return res.status(404).json({ error: 'product not found' });
      }
      res.json(result.rows[0]);
    } catch (error) {
      next(error);
    }
  });

  app.post('/inventory/reserve', async (req, res, next) => {
    const clientConnection = await pool.connect();
    try {
      const productId = Number(req.body.productId);
      const quantity = Number(req.body.quantity || 1);
      if (!Number.isInteger(productId) || productId < 1 || !Number.isInteger(quantity) || quantity < 1) {
        return res.status(400).json({ error: 'productId and quantity must be positive integers' });
      }

      await clientConnection.query('BEGIN');
      const current = await clientConnection.query(`
        SELECT quantity FROM inventory WHERE product_id = $1 FOR UPDATE
      `, [productId]);

      if (current.rowCount === 0) {
        await clientConnection.query('ROLLBACK');
        inventoryReserveFailureTotal.inc();
        return res.status(404).json({ error: 'product not found' });
      }

      if (Number(current.rows[0].quantity) < quantity) {
        await clientConnection.query('ROLLBACK');
        inventoryReserveFailureTotal.inc();
        return res.status(409).json({ error: 'insufficient inventory' });
      }

      const updated = await clientConnection.query(`
        UPDATE inventory
        SET quantity = quantity - $1, updated_at = now()
        WHERE product_id = $2
        RETURNING product_id, quantity
      `, [quantity, productId]);

      await clientConnection.query('COMMIT');
      inventoryReserveSuccessTotal.inc();
      res.status(201).json({ reservation: updated.rows[0] });
    } catch (error) {
      await clientConnection.query('ROLLBACK').catch(() => {});
      inventoryReserveFailureTotal.inc();
      next(error);
    } finally {
      clientConnection.release();
    }
  });

  app.post('/inventory/release', async (req, res, next) => {
    try {
      const productId = Number(req.body.productId);
      const quantity = Number(req.body.quantity || 1);
      if (!Number.isInteger(productId) || productId < 1 || !Number.isInteger(quantity) || quantity < 1) {
        return res.status(400).json({ error: 'productId and quantity must be positive integers' });
      }

      const updated = await pool.query(`
        UPDATE inventory
        SET quantity = quantity + $1, updated_at = now()
        WHERE product_id = $2
        RETURNING product_id, quantity
      `, [quantity, productId]);

      if (updated.rowCount === 0) {
        return res.status(404).json({ error: 'product not found' });
      }

      res.status(200).json({ release: updated.rows[0] });
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
    console.log(JSON.stringify({ level: 'info', service: 'inventory-service', message: 'server_started', port }));
  });

  async function shutdown(signal) {
    console.log(JSON.stringify({ level: 'info', service: 'inventory-service', message: 'shutdown_started', signal }));
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
