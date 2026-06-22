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
    CREATE TABLE IF NOT EXISTS payments (
      id SERIAL PRIMARY KEY,
      authorization_id TEXT NOT NULL UNIQUE,
      amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
      status TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
  `);
}

async function readinessCheck() {
  await pool.query('SELECT 1');
}

module.exports = { pool, initializeDatabase, readinessCheck };
