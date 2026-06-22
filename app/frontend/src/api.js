const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    },
    ...options
  });

  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(payload.error || `request failed with ${response.status}`);
  }

  return payload;
}

export function getProducts() {
  return request('/api/products');
}

export function getCart() {
  return request('/api/cart');
}

export function addToCart(productId, quantity = 1) {
  return request('/api/cart', {
    method: 'POST',
    body: JSON.stringify({ productId, quantity })
  });
}

export function checkout() {
  return request('/api/checkout', {
    method: 'POST',
    body: JSON.stringify({})
  });
}

export function getOrders() {
  return request('/api/orders');
}

export function setLatencyFault(latencyMs) {
  return request('/fault/latency', {
    method: 'POST',
    body: JSON.stringify({ latencyMs })
  });
}

export function setErrorRateFault(errorRate) {
  return request('/fault/error-rate', {
    method: 'POST',
    body: JSON.stringify({ errorRate })
  });
}

export function resetFaults() {
  return request('/fault/reset', {
    method: 'POST',
    body: JSON.stringify({})
  });
}
