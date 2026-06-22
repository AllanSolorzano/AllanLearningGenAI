const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const {
  client,
  metricsMiddleware,
  checkoutSuccessTotal,
  checkoutFailureTotal,
  setFaultMetric,
  resetFaultMetrics,
  shutdownTracing
} = require('./observability');

const port = Number(process.env.PORT || 8080);
const inventoryUrl = process.env.INVENTORY_SERVICE_URL || 'http://inventory-service:8080';
const orderUrl = process.env.ORDER_SERVICE_URL || 'http://order-service:8080';
const paymentUrl = process.env.PAYMENT_SERVICE_URL || 'http://payment-service:8080';
const inventoryTimeoutMs = Number(process.env.INVENTORY_SERVICE_TIMEOUT_MS || 3000);
const orderTimeoutMs = Number(process.env.ORDER_SERVICE_TIMEOUT_MS || 3000);
const paymentTimeoutMs = Number(process.env.PAYMENT_SERVICE_TIMEOUT_MS || 3000);
const paymentFallbackEnabled = String(process.env.PAYMENT_FALLBACK_ENABLED || 'false') === 'true';

const cart = new Map();
const faultState = { latencyMs: 0, errorRate: 0 };

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function requestLogger(req, res, next) {
  const startedAt = Date.now();
  res.on('finish', () => {
    console.log(JSON.stringify({
      level: 'info',
      service: 'api-gateway',
      method: req.method,
      path: req.originalUrl,
      status: res.statusCode,
      durationMs: Date.now() - startedAt
    }));
  });
  next();
}

function errorHandler(error, req, res, next) {
  if (res.headersSent) {
    return next(error);
  }

  console.error(JSON.stringify({
    level: 'error',
    service: 'api-gateway',
    message: error.message,
    stage: error.stage,
    path: req.originalUrl
  }));

  res.status(error.statusCode || 500).json({
    error: error.publicMessage || 'internal_error',
    stage: error.stage || null
  });
}

async function serviceFetch(baseUrl, path, options = {}, timeoutMs = 3000, stage = 'dependency') {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${baseUrl}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        'content-type': 'application/json',
        ...(options.headers || {})
      }
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(payload.error || `${stage} failed with ${response.status}`);
      error.statusCode = response.status >= 500 ? 502 : response.status;
      error.publicMessage = payload.error || `${stage}_failed`;
      error.stage = stage;
      throw error;
    }

    return payload;
  } catch (error) {
    if (error.name === 'AbortError') {
      error.message = `${stage} timed out`;
      error.publicMessage = `${stage}_timeout`;
      error.statusCode = 504;
    }
    error.stage = error.stage || stage;
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

function cartPayload(products = []) {
  const productById = new Map(products.map((product) => [Number(product.id), product]));
  const items = Array.from(cart.values()).map((item) => {
    const product = productById.get(item.productId);
    const priceCents = product ? Number(product.price_cents) : 0;
    return {
      product_id: item.productId,
      name: product ? product.name : `Product ${item.productId}`,
      quantity: item.quantity,
      price_cents: priceCents,
      line_total_cents: priceCents * item.quantity
    };
  });

  return {
    items,
    total_cents: items.reduce((sum, item) => sum + item.line_total_cents, 0)
  };
}

function faultInjectionMiddleware(req, res, next) {
  if (req.path.startsWith('/fault')) {
    return next();
  }

  Promise.resolve()
    .then(async () => {
      if (faultState.latencyMs > 0) {
        await sleep(faultState.latencyMs);
      }
      if (faultState.errorRate > 0 && Math.random() < faultState.errorRate) {
        const error = new Error('injected Arena fault');
        error.statusCode = 503;
        error.publicMessage = 'injected_fault';
        throw error;
      }
    })
    .then(() => next())
    .catch(next);
}

async function readyCheck() {
  await Promise.all([
    serviceFetch(inventoryUrl, '/ready', {}, inventoryTimeoutMs, 'inventory_ready'),
    serviceFetch(orderUrl, '/ready', {}, orderTimeoutMs, 'order_ready'),
    serviceFetch(paymentUrl, '/ready', {}, paymentTimeoutMs, 'payment_ready')
  ]);
}

const app = express();
app.disable('x-powered-by');
app.use(helmet());
app.use(cors());
app.use(express.json({ limit: '64kb' }));
app.use(requestLogger);
app.use(metricsMiddleware);
app.use(faultInjectionMiddleware);

app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'api-gateway' });
});

app.get('/ready', async (req, res, next) => {
  try {
    await readyCheck();
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

app.get('/api/products', async (req, res, next) => {
  try {
    res.json(await serviceFetch(inventoryUrl, '/products', {}, inventoryTimeoutMs, 'list_products'));
  } catch (error) {
    next(error);
  }
});

app.get('/api/cart', async (req, res, next) => {
  try {
    const { products } = await serviceFetch(inventoryUrl, '/products', {}, inventoryTimeoutMs, 'list_products');
    res.json(cartPayload(products));
  } catch (error) {
    next(error);
  }
});

app.post('/api/cart', async (req, res, next) => {
  try {
    const productId = Number(req.body.productId);
    const quantity = Number(req.body.quantity || 1);

    if (!Number.isInteger(productId) || productId < 1) {
      return res.status(400).json({ error: 'productId must be a positive integer' });
    }
    if (!Number.isInteger(quantity) || quantity < 1 || quantity > 25) {
      return res.status(400).json({ error: 'quantity must be between 1 and 25' });
    }

    await serviceFetch(inventoryUrl, `/inventory/${productId}`, {}, inventoryTimeoutMs, 'check_inventory');
    const current = cart.get(productId) || { productId, quantity: 0 };
    current.quantity += quantity;
    cart.set(productId, current);

    const { products } = await serviceFetch(inventoryUrl, '/products', {}, inventoryTimeoutMs, 'list_products');
    res.status(201).json(cartPayload(products));
  } catch (error) {
    next(error);
  }
});

app.post('/api/checkout', async (req, res, next) => {
  const items = Array.from(cart.values());
  if (items.length === 0) {
    return res.status(400).json({ error: 'cart is empty' });
  }

  const reservedItems = [];

  try {
    const enrichedItems = [];
    for (const item of items) {
      const inventory = await serviceFetch(
        inventoryUrl,
        `/inventory/${item.productId}`,
        {},
        inventoryTimeoutMs,
        'check_inventory'
      );
      enrichedItems.push({
        productId: item.productId,
        quantity: item.quantity,
        priceCents: Number(inventory.price_cents)
      });
    }

    for (const item of enrichedItems) {
      await serviceFetch(
        inventoryUrl,
        '/inventory/reserve',
        {
          method: 'POST',
          body: JSON.stringify({ productId: item.productId, quantity: item.quantity })
        },
        inventoryTimeoutMs,
        'reserve_inventory'
      );
      reservedItems.push(item);
    }

    const totalCents = enrichedItems.reduce((sum, item) => sum + item.priceCents * item.quantity, 0);
    let payment = null;

    try {
      payment = await serviceFetch(
        paymentUrl,
        '/payment/authorize',
        {
          method: 'POST',
          body: JSON.stringify({ amountCents: totalCents })
        },
        paymentTimeoutMs,
        'authorize_payment'
      );
    } catch (error) {
      if (!paymentFallbackEnabled) {
        throw error;
      }
      payment = { authorizationId: 'fallback-not-authorized', status: 'fallback' };
    }

    const order = await serviceFetch(
      orderUrl,
      '/checkout',
      {
        method: 'POST',
        body: JSON.stringify({ items: enrichedItems, payment })
      },
      orderTimeoutMs,
      'create_order'
    );

    cart.clear();
    checkoutSuccessTotal.inc();
    res.status(201).json(order);
  } catch (error) {
    for (const item of reservedItems) {
      try {
        await serviceFetch(
          inventoryUrl,
          '/inventory/release',
          {
            method: 'POST',
            body: JSON.stringify({ productId: item.productId, quantity: item.quantity })
          },
          inventoryTimeoutMs,
          'release_inventory'
        );
      } catch (releaseError) {
        console.error(JSON.stringify({
          level: 'error',
          service: 'api-gateway',
          message: 'failed to release reserved inventory after checkout failure',
          originalStage: error.stage || 'unknown',
          releaseStage: releaseError.stage || 'release_inventory',
          productId: item.productId
        }));
      }
    }
    checkoutFailureTotal.inc({ stage: error.stage || 'unknown' });
    next(error);
  }
});

app.get('/api/orders', async (req, res, next) => {
  try {
    res.json(await serviceFetch(orderUrl, '/orders', {}, orderTimeoutMs, 'list_orders'));
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
  console.log(JSON.stringify({ level: 'info', service: 'api-gateway', message: 'server_started', port }));
});

async function shutdown(signal) {
  console.log(JSON.stringify({ level: 'info', service: 'api-gateway', message: 'shutdown_started', signal }));
  server.close(async () => {
    await shutdownTracing();
    process.exit(0);
  });
}

process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
