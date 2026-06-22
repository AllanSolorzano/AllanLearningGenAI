const { Pool } = require('pg');

const pool = new Pool({
  host: process.env.DB_HOST || 'localhost',
  port: Number(process.env.DB_PORT || 5432),
  database: process.env.DB_NAME || 'chaos_store',
  user: process.env.DB_USER || 'postgres',
  password: process.env.DB_PASSWORD || 'postgres',
  max: Number(process.env.DB_POOL_SIZE || 10),
  connectionTimeoutMillis: 3000
});

async function initializeDatabase() {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS orders (
      id SERIAL PRIMARY KEY,
      status TEXT NOT NULL DEFAULT 'created',
      total_cents INTEGER NOT NULL DEFAULT 0 CHECK (total_cents >= 0),
      payment_authorization_id TEXT,
      payment_status TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS order_items (
      order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
      product_id INTEGER NOT NULL,
      quantity INTEGER NOT NULL CHECK (quantity > 0),
      price_cents INTEGER NOT NULL CHECK (price_cents > 0),
      PRIMARY KEY (order_id, product_id)
    );
  `);
}

async function readinessCheck() {
  await pool.query('SELECT 1');
}

async function withTransaction(callback) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const result = await callback(client);
    await client.query('COMMIT');
    return result;
  } catch (error) {
    await client.query('ROLLBACK');
    throw error;
  } finally {
    client.release();
  }
}

module.exports = { pool, initializeDatabase, readinessCheck, withTransaction };
