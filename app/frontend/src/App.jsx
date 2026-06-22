import { useEffect, useMemo, useState } from 'react';
import {
  addToCart,
  checkout,
  getCart,
  getOrders,
  getProducts,
  resetFaults,
  setErrorRateFault,
  setLatencyFault
} from './api';

function dollars(cents) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD'
  }).format(cents / 100);
}

export default function App() {
  const [products, setProducts] = useState([]);
  const [cart, setCart] = useState({ items: [], total_cents: 0 });
  const [orders, setOrders] = useState([]);
  const [message, setMessage] = useState('Ready for steady-state checks.');
  const [loading, setLoading] = useState(false);
  const [latencyMs, setLatencyMs] = useState(750);
  const [errorRate, setErrorRate] = useState(0.25);

  async function refresh() {
    const [productPayload, cartPayload, orderPayload] = await Promise.all([
      getProducts(),
      getCart(),
      getOrders()
    ]);

    setProducts(productPayload.products);
    setCart(cartPayload);
    setOrders(orderPayload.orders || []);
  }

  useEffect(() => {
    refresh().catch((error) => setMessage(error.message));
  }, []);

  const cartCount = useMemo(
    () => cart.items.reduce((sum, item) => sum + Number(item.quantity), 0),
    [cart]
  );

  async function runAction(action, successMessage) {
    setLoading(true);
    try {
      await action();
      await refresh();
      setMessage(successMessage);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="shell">
      <section className="status-bar" aria-label="Store status">
        <div>
          <p className="eyebrow">AI Chaos GameDay</p>
          <h1>Steady-State Store</h1>
        </div>
        <div className="status-pill">
          <span>{cartCount}</span>
          <small>items</small>
        </div>
      </section>

      <section className="layout">
        <div className="products" aria-label="Products">
          {products.map((product) => (
            <article className="product" key={product.id}>
              <div>
                <h2>{product.name}</h2>
                <p>{product.description}</p>
              </div>
              <div className="product-actions">
                <strong>{dollars(product.price_cents)}</strong>
                <button
                  disabled={loading}
                  onClick={() => runAction(
                    () => addToCart(product.id),
                    `${product.name} added to cart.`
                  )}
                >
                  Add
                </button>
              </div>
            </article>
          ))}
        </div>

        <aside className="panel" aria-label="Cart and faults">
          <div>
            <h2>Cart</h2>
            {cart.items.length === 0 ? (
              <p className="muted">No items yet.</p>
            ) : (
              <ul className="cart-list">
                {cart.items.map((item) => (
                  <li key={item.product_id}>
                    <span>{item.name} x {item.quantity}</span>
                    <strong>{dollars(item.line_total_cents)}</strong>
                  </li>
                ))}
              </ul>
            )}
            <div className="total">
              <span>Total</span>
              <strong>{dollars(cart.total_cents || 0)}</strong>
            </div>
            <button
              className="primary"
              disabled={loading || cart.items.length === 0}
              onClick={() => runAction(checkout, 'Checkout completed. Watch the traces and metrics.')}
            >
              Checkout
            </button>
          </div>

          <div className="faults">
            <h2>Fault Controls</h2>
            <label>
              Latency ms
              <input
                type="number"
                min="0"
                max="5000"
                value={latencyMs}
                onChange={(event) => setLatencyMs(Number(event.target.value))}
              />
            </label>
            <button
              disabled={loading}
              onClick={() => runAction(
                () => setLatencyFault(latencyMs),
                `Latency fault set to ${latencyMs} ms.`
              )}
            >
              Apply Latency
            </button>

            <label>
              Error rate
              <input
                type="number"
                min="0"
                max="1"
                step="0.05"
                value={errorRate}
                onChange={(event) => setErrorRate(Number(event.target.value))}
              />
            </label>
            <button
              disabled={loading}
              onClick={() => runAction(
                () => setErrorRateFault(errorRate),
                `Error-rate fault set to ${errorRate}.`
              )}
            >
              Apply Errors
            </button>
            <button
              className="secondary"
              disabled={loading}
              onClick={() => runAction(resetFaults, 'Faults reset.')}
            >
              Reset Faults
            </button>
          </div>

          <div>
            <h2>Recent Orders</h2>
            {orders.length === 0 ? (
              <p className="muted">No orders yet.</p>
            ) : (
              <ul className="cart-list">
                {orders.slice(0, 5).map((order) => (
                  <li key={order.id}>
                    <span>#{order.id} {order.status}</span>
                    <strong>{dollars(order.total_cents)}</strong>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>
      </section>

      <section className="message" aria-live="polite">
        {loading ? 'Working...' : message}
      </section>
    </main>
  );
}
