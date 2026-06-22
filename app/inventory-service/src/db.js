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
    CREATE TABLE IF NOT EXISTS products (
      id SERIAL PRIMARY KEY,
      name TEXT NOT NULL UNIQUE,
      description TEXT NOT NULL,
      price_cents INTEGER NOT NULL CHECK (price_cents > 0),
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE IF NOT EXISTS inventory (
      product_id INTEGER PRIMARY KEY REFERENCES products(id) ON DELETE CASCADE,
      quantity INTEGER NOT NULL CHECK (quantity >= 0),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    INSERT INTO products (name, description, price_cents)
    VALUES
      ('Steady State Mug', 'A coffee mug for calm incident reviews.', 1800),
      ('Blast Radius Notebook', 'A field notebook for experiment hypotheses.', 1200),
      ('Latency Hoodie', 'A soft hoodie for waiting out packet delay.', 4200),
      ('Rollback Sticker Pack', 'Five stickers for resilient laptops.', 700)
    ON CONFLICT (name) DO NOTHING;

    INSERT INTO inventory (product_id, quantity)
    SELECT id,
      CASE name
        WHEN 'Steady State Mug' THEN 75
        WHEN 'Blast Radius Notebook' THEN 120
        WHEN 'Latency Hoodie' THEN 40
        ELSE 250
      END
    FROM products
    ON CONFLICT (product_id) DO NOTHING;
  `);
}

async function readinessCheck() {
  await pool.query('SELECT 1');
}

module.exports = { pool, initializeDatabase, readinessCheck };
