---
name: Webapp Testing
description: Playwright testing with autonomous test agents (planner, generator, healer) and visual regression testing
version: 1.1.0
tags: [playwright, testing, e2e, automation, agents, visual-regression, 2025]
---

# Webapp Testing Skill

Autonomous end-to-end testing with Playwright's three specialized agents plus native visual regression testing.

## The Three Agents

1. **Planner** - Explores app and creates test plans
2. **Generator** - Writes Playwright tests with best practices
3. **Healer** - Fixes failing tests automatically

## Quick Setup

```bash
# 1. Install Playwright
npm install --save-dev @playwright/test

# 2. Add MCP server
claude mcp add playwright npx '@playwright/mcp@latest'

# 3. Initialize agents
npx playwright init-agents --loop=claude

# 4. Create tests/seed.spec.ts (required for Planner)
```

**Requirements:** VS Code v1.105+ (Oct 9, 2025) or Claude Desktop with Playwright MCP

## Agent Workflow

```
1. PLANNER   ──▶ Explores app ──▶ Creates specs/checkout.md
                 (uses seed.spec.ts)
                      │
                      ▼
2. GENERATOR ──▶ Reads spec ──▶ Tests live app ──▶ Outputs tests/checkout.spec.ts
                 (verifies selectors actually work)
                      │
                      ▼
3. HEALER    ──▶ Runs tests ──▶ Fixes failures ──▶ Updates selectors/waits
                 (self-healing)
```

## Directory Structure

```
your-project/
├── specs/              ← Planner outputs (Markdown plans)
├── tests/              ← Generator outputs (Playwright tests)
│   └── seed.spec.ts    ← Required: Planner learns from this
├── playwright.config.ts
└── screenshots/        ← Visual regression baselines
    ├── desktop/
    └── mobile/
```

## Key Concepts

**seed.spec.ts is required** - Planner executes this to learn:
- Environment setup (fixtures, hooks)
- Authentication flow
- Available UI elements

**Generator validates live** - Doesn't just translate Markdown, actually tests app to verify selectors work.

**Healer auto-fixes** - When UI changes break tests, Healer replays, finds new selectors, patches tests.

---

## Visual Regression Testing

**Replace Percy with Playwright's native screenshot testing** (zero cost, faster, better).

### Basic Visual Test

```typescript
import { test, expect } from '@playwright/test';

test('homepage visual regression', async ({ page }) => {
  await page.goto('/');
  
  // Full page screenshot with auto-retry
  await expect(page).toHaveScreenshot('homepage.png', {
    fullPage: true,
    maxDiffPixels: 100,  // Allow small rendering differences
  });
});
```

### Component-Level Visual Testing

```typescript
test('product card visual', async ({ page }) => {
  await page.goto('/products');
  
  // Screenshot specific component
  const productCard = page.locator('.product-card').first();
  await expect(productCard).toHaveScreenshot('product-card.png', {
    maxDiffPixelRatio: 0.01,  // 1% tolerance
  });
});
```

### Responsive Visual Testing

```typescript
const viewports = [
  { name: 'mobile', width: 375, height: 667 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1920, height: 1080 },
];

for (const viewport of viewports) {
  test(`homepage ${viewport.name}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.goto('/');
    
    await expect(page).toHaveScreenshot(`homepage-${viewport.name}.png`);
  });
}
```

### Masking Dynamic Content

```typescript
test('dashboard with masked content', async ({ page }) => {
  await page.goto('/dashboard');
  
  await expect(page).toHaveScreenshot('dashboard.png', {
    mask: [
      page.locator('.timestamp'),      // Hide timestamps
      page.locator('.user-avatar'),    // Hide user photos
      page.locator('.live-graph'),     // Hide real-time data
    ],
  });
});
```

### CI/CD Integration

**playwright.config.ts:**
```typescript
export default defineConfig({
  // Update screenshots in CI when expected
  updateSnapshots: process.env.CI ? 'none' : 'missing',
  
  // Relaxed thresholds for cross-platform consistency
  expect: {
    toHaveScreenshot: {
      maxDiffPixels: 100,
      threshold: 0.2,  // 20% tolerance
    },
  },
  
  // Separate screenshot storage by OS
  snapshotPathTemplate: '{testDir}/__screenshots__/{platform}/{projectName}/{testFilePath}/{arg}{ext}',
});
```

**GitHub Actions:**
```yaml
- name: Run Playwright tests
  run: npx playwright test
  
- name: Upload visual diffs on failure
  if: failure()
  uses: actions/upload-artifact@v3
  with:
    name: playwright-visual-diffs
    path: test-results/
```

### Updating Baselines

```bash
# Update all screenshots
npx playwright test --update-snapshots

# Update specific test screenshots
npx playwright test homepage.spec.ts --update-snapshots

# Review diffs before updating
npx playwright show-report
```

---

## Real-World Test Examples

### E-commerce Checkout Flow

```typescript
test('complete checkout flow', async ({ page }) => {
  // Add item to cart
  await page.goto('/products');
  await page.click('[data-testid="add-to-cart-123"]');
  
  // Visual: Cart icon badge
  await expect(page.locator('.cart-badge')).toHaveScreenshot('cart-badge-1-item.png');
  
  // Proceed to checkout
  await page.click('[data-testid="cart-icon"]');
  await expect(page).toHaveScreenshot('cart-page.png', {
    mask: [page.locator('.item-price')],  // Prices may change
  });
  
  // Fill shipping info
  await page.fill('[name="email"]', 'test@example.com');
  await page.fill('[name="address"]', '123 Main St');
  
  // Visual: Filled form
  await expect(page.locator('.checkout-form')).toHaveScreenshot('checkout-form-filled.png');
  
  // Submit order
  await page.click('button[type="submit"]');
  await page.waitForURL('**/order-confirmation/**');
  
  // Visual: Confirmation page
  await expect(page).toHaveScreenshot('order-confirmation.png', {
    mask: [page.locator('.order-id'), page.locator('.timestamp')],
  });
});
```

### Dashboard with Real-time Data

```typescript
test('analytics dashboard', async ({ page }) => {
  await page.goto('/dashboard');
  
  // Wait for data to load
  await page.waitForSelector('[data-loaded="true"]');
  
  // Mask all dynamic content
  await expect(page).toHaveScreenshot('dashboard.png', {
    mask: [
      page.locator('.live-counter'),
      page.locator('.timestamp'),
      page.locator('.chart-canvas'),  // Charts with live data
      page.locator('[data-dynamic="true"]'),
    ],
  });
});
```

### Dark Mode Theme Testing

```typescript
const themes = ['light', 'dark'];

for (const theme of themes) {
  test(`homepage ${theme} theme`, async ({ page }) => {
    await page.goto('/');
    
    // Toggle theme
    await page.evaluate((t) => {
      document.documentElement.setAttribute('data-theme', t);
    }, theme);
    
    // Wait for CSS transitions
    await page.waitForTimeout(500);
    
    await expect(page).toHaveScreenshot(`homepage-${theme}.png`);
  });
}
```

---

## Best Practices

### Visual Regression

1. **Use meaningful names**: `checkout-step-2-payment.png` not `screen-1.png`
2. **Mask dynamic content**: Timestamps, user data, live graphs
3. **Set appropriate thresholds**: `maxDiffPixels: 100` for pixel-perfect, `maxDiffPixelRatio: 0.02` for 2% tolerance
4. **Test critical paths only**: Don't screenshot every page
5. **Group by viewport**: Separate screenshots for mobile/tablet/desktop
6. **Review diffs in CI**: Upload artifacts on failure for manual review

### Agent Usage

1. **Start with seed.spec.ts**: Teach Planner your auth flow and common patterns
2. **Let Generator validate**: Don't manually write selectors, let it test the live app
3. **Trust the Healer**: When selectors break, Healer finds new ones automatically
4. **Iterate on specs**: Update Markdown specs, regenerate tests

See `references/` for detailed agent patterns and visual regression setup.

---

**Version:** 1.1.0 (December 2025)
**MCP Requirement:** Playwright MCP server
**Visual Regression:** Native Playwright `toHaveScreenshot()` (no Percy needed)
