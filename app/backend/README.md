# Backend Services

This folder groups the ResilienceMart backend microservices:

- `api-gateway`: public BFF/API entry point for the frontend.
- `inventory-service`: product catalog, stock lookup, and reservation.
- `order-service`: order creation and order lookup.
- `payment-service`: mock payment authorization dependency.

There is no deployable service named `backend`. Kubernetes deploys each microservice independently.
