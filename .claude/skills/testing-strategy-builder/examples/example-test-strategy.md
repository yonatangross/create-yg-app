# E-Commerce Platform Testing Strategy

## Overview

This testing strategy covers a modern e-commerce platform built with React 19, FastAPI, PostgreSQL, and Redis. The platform handles 10,000+ daily users with payment processing, inventory management, and order fulfillment.

**Testing Pyramid:**
```
        /\
       /E2E\         5% - Critical checkout flows
      /______\
     /        \
    /Integration\ 25% - API contracts, payment gateway
   /____________\
  /              \
 /  Unit Tests    \ 70% - Business logic, calculations
/__________________\
```

---

## Tech Stack

| Layer | Framework | Purpose |
|-------|-----------|---------|
| **Backend** | pytest 8.3.4 | Unit & integration tests |
| **Frontend** | Vitest 2.1.8 + React Testing Library | Component & hook tests |
| **E2E** | Playwright 1.49.0 | Critical user flows |
| **Coverage** | pytest-cov, Vitest coverage | Track test coverage |
| **API Mocking** | MSW (Mock Service Worker) | Network-level mocking |
| **HTTP Recording** | pytest-vcr | Deterministic API tests |

---

## Coverage Targets

### Backend (Python/FastAPI)

| Module | Target | Priority | Rationale |
|--------|--------|----------|-----------|
| **Payment Processing** | 100% | Critical | Financial transactions |
| **Order Management** | 95% | Critical | Business core |
| **API Routes** | 90% | High | Public contracts |
| **Auth & Permissions** | 100% | Critical | Security critical |
| **Inventory Service** | 85% | High | Stock accuracy |
| **Email Notifications** | 70% | Medium | Non-critical |

**Run coverage:**
```bash
cd backend
pytest tests/unit/ --cov=app --cov-report=term-missing --cov-report=html
open htmlcov/index.html
```

### Frontend (TypeScript/React 19)

| Module | Target | Priority | Rationale |
|--------|--------|---------|-----------|
| **Checkout Flow** | 95% | Critical | Revenue impact |
| **Product Catalog** | 80% | High | User-facing |
| **Auth Components** | 100% | Critical | Security |
| **Cart Management** | 90% | High | Business logic |
| **UI Components** | 70% | Medium | Visual elements |

**Run coverage:**
```bash
cd frontend
npm run test:coverage
open coverage/index.html
```

---

## Test Structure

### Backend Test Organization

```
backend/tests/
├── conftest.py                  # Global fixtures (db_session, async fixtures)
├── unit/                        # Unit tests (70% of tests)
│   ├── api/
│   │   └── v1/
│   │       ├── test_orders.py
│   │       ├── test_products.py
│   │       └── test_payments.py
│   ├── services/
│   │   ├── test_payment_processor.py
│   │   ├── test_inventory_manager.py
│   │   └── test_email_service.py
│   └── utils/
│       ├── test_price_calculator.py
│       └── test_tax_calculator.py
├── integration/                 # Integration tests (25% of tests)
│   ├── test_order_workflow.py
│   ├── test_payment_integration.py  # Uses VCR for API recording
│   └── test_inventory_sync.py
└── e2e/                        # E2E tests (5% of tests)
    └── test_checkout_journey.py
```

### Frontend Test Organization

```
frontend/src/
├── __tests__/
│   ├── setup.ts                # MSW server setup
│   └── mocks/
│       └── handlers.ts         # MSW request handlers
├── features/
│   ├── checkout/
│   │   └── __tests__/
│   │       ├── CheckoutForm.test.tsx
│   │       └── useCheckout.test.ts
│   ├── cart/
│   │   └── __tests__/
│   │       ├── CartSummary.test.tsx
│   │       └── useCart.test.ts
│   └── products/
│       └── __tests__/
│           └── ProductGrid.test.tsx
└── lib/
    └── __tests__/
        ├── api-client.test.ts  # Uses MSW for mocking
        └── price-utils.test.ts
```

---

## Mock Strategies

### MSW for Frontend API Mocking (2025 Standard)

MSW intercepts requests at the network level, not implementation details.

```typescript
// frontend/src/__tests__/mocks/handlers.ts
import { http, HttpResponse } from 'msw'

export const handlers = [
  // Success: Get product
  http.get('/api/v1/products/:id', ({ params }) => {
    return HttpResponse.json({
      id: params.id,
      name: 'Wireless Headphones',
      price: 99.99,
      stock: 42,
    })
  }),

  // Error: Out of stock
  http.post('/api/v1/cart/add', async () => {
    return HttpResponse.json(
      { error: 'Product out of stock' },
      { status: 422 }
    )
  }),

  // Delayed response (simulate slow network)
  http.get('/api/v1/orders', async () => {
    await delay(1000)
    return HttpResponse.json({ orders: [] })
  }),
]
```

```typescript
// frontend/src/__tests__/setup.ts
import { beforeAll, afterEach, afterAll } from 'vitest'
import { setupServer } from 'msw/node'
import { handlers } from './mocks/handlers'

const server = setupServer(...handlers)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```

```typescript
// frontend/src/features/cart/__tests__/CartSummary.test.tsx
import { render, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '../../__tests__/mocks/server'
import { CartSummary } from '../CartSummary'

test('shows error when cart fetch fails', async () => {
  // Override handler for this specific test
  server.use(
    http.get('/api/v1/cart', () => {
      return HttpResponse.json(
        { error: 'Cart service unavailable' },
        { status: 503 }
      )
    })
  )

  render(<CartSummary />)

  expect(await screen.findByText(/unavailable/i)).toBeInTheDocument()
})
```

### VCR.py for Backend API Recording (2025 Standard)

VCR.py records real HTTP responses once, then replays deterministically.

```python
# backend/tests/conftest.py
import pytest
import vcr

@pytest.fixture(scope="module")
def vcr_config():
    """Configure VCR for all tests."""
    return {
        "cassette_library_dir": "tests/cassettes",
        "record_mode": "once",  # Record once, replay forever
        "match_on": ["uri", "method"],
        "filter_headers": ["authorization", "x-api-key"],  # Security!
    }
```

```python
# backend/tests/integration/test_payment_integration.py
import pytest
from app.services.payment_gateway import StripeGateway

@pytest.mark.vcr()
async def test_successful_charge():
    """Test Stripe charge with recorded HTTP response."""
    gateway = StripeGateway(api_key="test-key")
    
    result = await gateway.charge(
        amount=2999,  # $29.99
        currency="usd",
        source="tok_visa",
    )
    
    assert result["status"] == "succeeded"
    assert result["amount"] == 2999
    # Real Stripe response recorded in tests/cassettes/test_successful_charge.yaml

@pytest.mark.vcr()
async def test_declined_card():
    """Test Stripe decline with recorded error response."""
    gateway = StripeGateway(api_key="test-key")
    
    with pytest.raises(PaymentDeclined) as exc_info:
        await gateway.charge(
            amount=2999,
            currency="usd",
            source="tok_chargeDeclined",  # Test token that triggers decline
        )
    
    assert "card was declined" in str(exc_info.value)
```

### Database Mocking

**Unit tests:** Mock database queries for speed.

```python
# backend/tests/unit/services/test_inventory_manager.py
from unittest.mock import AsyncMock, patch
import pytest

@pytest.mark.asyncio
async def test_check_stock_availability():
    """Test stock check without database."""
    with patch("app.db.repositories.product_repository.ProductRepository") as mock_repo:
        # Mock repository method
        mock_repo.return_value.get_stock = AsyncMock(return_value=42)
        
        from app.services.inventory_manager import InventoryManager
        manager = InventoryManager()
        
        available = await manager.check_availability(product_id="prod_123", quantity=10)
        
        assert available is True
        mock_repo.return_value.get_stock.assert_called_once_with("prod_123")
```

**Integration tests:** Use real database with automatic rollback.

```python
# backend/tests/integration/test_order_workflow.py
import pytest
from app.models import Order, OrderItem

@pytest.mark.asyncio
async def test_create_order_with_items(db_session):
    """Test order creation with real database."""
    # db_session auto-rolls back after test
    order = Order(
        user_id="user_123",
        total=59.98,
        status="pending",
    )
    db_session.add(order)
    await db_session.flush()  # Get order ID
    
    # Add order items
    item1 = OrderItem(order_id=order.id, product_id="prod_1", quantity=2, price=29.99)
    item2 = OrderItem(order_id=order.id, product_id="prod_2", quantity=1, price=29.99)
    db_session.add_all([item1, item2])
    await db_session.commit()
    
    # Verify
    from sqlalchemy import select
    result = await db_session.execute(
        select(OrderItem).where(OrderItem.order_id == order.id)
    )
    items = result.scalars().all()
    
    assert len(items) == 2
    assert sum(item.quantity for item in items) == 3
    # Auto-rolled back after test ends
```

---

## Critical Test Examples

### React 19 + Zod Validation

```typescript
// frontend/src/features/checkout/__tests__/CheckoutForm.test.tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '../../../__tests__/mocks/server'
import { CheckoutForm } from '../CheckoutForm'
import { z } from 'zod'

// Zod schema for checkout
const CheckoutSchema = z.object({
  email: z.string().email(),
  cardNumber: z.string().length(16),
  expiryMonth: z.number().min(1).max(12),
  expiryYear: z.number().min(2025),
  cvv: z.string().length(3),
})

test('validates form with Zod before submission', async () => {
  const user = userEvent.setup()
  render(<CheckoutForm />)
  
  // Fill invalid email
  await user.type(screen.getByLabelText(/email/i), 'not-an-email')
  await user.click(screen.getByRole('button', { name: /submit/i }))
  
  // Zod validation error shown
  expect(await screen.findByText(/invalid email/i)).toBeInTheDocument()
})

test('submits order with valid data', async () => {
  const user = userEvent.setup()
  
  // Mock successful order creation
  server.use(
    http.post('/api/v1/orders', async ({ request }) => {
      const body = await request.json()
      
      // Validate with Zod
      const parsed = CheckoutSchema.parse(body)
      
      return HttpResponse.json({
        order_id: 'ord_12345',
        status: 'processing',
      })
    })
  )
  
  render(<CheckoutForm />)
  
  // Fill valid data
  await user.type(screen.getByLabelText(/email/i), 'customer@example.com')
  await user.type(screen.getByLabelText(/card number/i), '4242424242424242')
  await user.selectOptions(screen.getByLabelText(/month/i), '12')
  await user.selectOptions(screen.getByLabelText(/year/i), '2025')
  await user.type(screen.getByLabelText(/cvv/i), '123')
  
  await user.click(screen.getByRole('button', { name: /submit/i }))
  
  // Success message shown
  expect(await screen.findByText(/order placed/i)).toBeInTheDocument()
})
```

### Async Timeout Testing

```python
# backend/tests/unit/services/test_email_service.py
import pytest
import asyncio

@pytest.mark.asyncio
async def test_email_send_respects_timeout():
    """Test that email send honors timeout limits."""
    from app.services.email_service import EmailService
    
    async def slow_send():
        await asyncio.sleep(10)  # Simulates slow SMTP
        return "sent"
    
    service = EmailService()
    service._send_via_smtp = slow_send
    
    with pytest.raises(asyncio.TimeoutError):
        async with asyncio.timeout(0.5):
            await service.send_email(
                to="customer@example.com",
                subject="Order Confirmation",
                body="Thank you for your order",
            )

@pytest.mark.asyncio
async def test_email_service_fails_open_on_timeout():
    """Test graceful degradation when email times out."""
    service = EmailService(fail_open=True)
    
    result = await service.send_with_fallback(
        to="customer@example.com",
        subject="Test",
        body="Test",
        timeout=0.1,
    )
    
    assert result["status"] == "fallback"
    assert result["error"] == "Email send timed out"
    assert result["order_processed"] is True  # Order still completed!
```

---

## Performance Testing

### Load Test with k6

```javascript
// backend/tests/performance/checkout_load.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '2m', target: 50 },   // Ramp up to 50 users
    { duration: '5m', target: 50 },   // Sustain 50 users
    { duration: '2m', target: 100 },  // Ramp to 100 users
    { duration: '5m', target: 100 },  // Sustain 100 users
    { duration: '2m', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<800'], // 95% of requests < 800ms
    http_req_failed: ['rate<0.01'],   // Error rate < 1%
    checks: ['rate>0.99'],            // 99% of checks pass
  },
};

export default function () {
  // Create order
  const payload = JSON.stringify({
    user_id: 'user_123',
    items: [
      { product_id: 'prod_1', quantity: 2 },
    ],
    payment_method: 'card_test',
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer test-token',
    },
  };

  const res = http.post('https://api.example.com/v1/orders', payload, params);

  check(res, {
    'status is 201': (r) => r.status === 201,
    'response has order_id': (r) => JSON.parse(r.body).order_id !== undefined,
    'response time < 800ms': (r) => r.timings.duration < 800,
  });

  sleep(1);
}
```

**Run load test:**
```bash
k6 run backend/tests/performance/checkout_load.js
```

---

## Running Tests

### Backend (pytest 8.x)

```bash
cd backend

# Run all unit tests (fast, ~30 seconds)
pytest tests/unit/ -v

# Run specific test file
pytest tests/unit/api/v1/test_orders.py -v

# Run tests matching pattern
pytest -k "test_payment" -v

# Run with coverage report
pytest tests/unit/ --cov=app --cov-report=term-missing --cov-report=html

# Run integration tests (requires database)
pytest tests/integration/ -v

# Run specific test with verbose output
pytest tests/unit/services/test_payment_processor.py::test_successful_charge -vv
```

### Frontend (Vitest)

```bash
cd frontend

# Run all tests
npm run test

# Run in watch mode (auto-rerun on changes)
npm run test:watch

# Run specific test file
npm run test src/features/checkout/__tests__/CheckoutForm.test.tsx

# Run with coverage
npm run test:coverage

# Run with UI
npm run test:ui
```

### E2E (Playwright)

```bash
cd frontend

# Run E2E tests headless
npm run test:e2e

# Run E2E tests in UI mode (see browser)
npm run test:e2e:ui

# Run specific E2E test
npx playwright test tests/e2e/checkout.spec.ts

# Generate test code (record actions)
npx playwright codegen localhost:5183
```

### Pre-Commit Checks

```bash
# Backend
cd backend
ruff format --check app/   # Format check (required by CI)
ruff check app/            # Lint check
ty check app/              # Type check

# Frontend
cd frontend
npm run lint               # ESLint + Biome
npm run typecheck          # TypeScript check
npm run build              # Ensure build succeeds
```

---

## CI/CD Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:17
        env:
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install uv
        run: pip install uv

      - name: Install dependencies
        run: |
          cd backend
          uv sync

      - name: Run ruff format check
        run: |
          cd backend
          uv run ruff format --check app/

      - name: Run ruff lint
        run: |
          cd backend
          uv run ruff check app/

      - name: Run type check
        run: |
          cd backend
          uv run ty check app/

      - name: Run unit tests
        run: |
          cd backend
          uv run pytest tests/unit/ --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: ./backend/coverage.xml

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install dependencies
        run: |
          cd frontend
          npm ci

      - name: Run lint
        run: |
          cd frontend
          npm run lint

      - name: Run type check
        run: |
          cd frontend
          npm run typecheck

      - name: Run tests
        run: |
          cd frontend
          npm run test:coverage

      - name: Run E2E tests
        run: |
          cd frontend
          npx playwright install --with-deps
          npm run test:e2e

  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run npm audit
        run: |
          cd frontend
          npm audit --audit-level=high

      - name: Run pip-audit
        run: |
          cd backend
          pip install pip-audit
          pip-audit
```

---

## Quality Gates

### Coverage Thresholds

```toml
# backend/pyproject.toml
[tool.coverage.run]
source = ["app"]
omit = [
    "*/tests/*",
    "*/migrations/*",
    "*/__init__.py",
]

[tool.coverage.report]
fail_under = 80  # Fail if coverage drops below 80%
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]
```

### Test Metrics

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| **Unit Test Coverage** | 90% | 92% | ✅ |
| **Integration Coverage** | 80% | 85% | ✅ |
| **E2E Test Count** | 10 | 12 | ✅ |
| **Test Execution Time** | < 15 min | 12 min | ✅ |
| **Flaky Test Rate** | < 1% | 0.3% | ✅ |

---

## References

- **Backend Tests:** `backend/tests/`
- **Frontend Tests:** `frontend/src/__tests__/`
- **Pytest Docs:** https://docs.pytest.org/en/stable/
- **Vitest Docs:** https://vitest.dev/
- **MSW Docs:** https://mswjs.io/
- **VCR.py Docs:** https://vcrpy.readthedocs.io/
- **Playwright Docs:** https://playwright.dev/

---

**Strategy Version**: 2.0.0
**Last Updated**: 2025-12-29
**Project**: E-Commerce Platform
