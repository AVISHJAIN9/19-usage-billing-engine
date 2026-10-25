import os

def generate_vitepress_config(docs_dir: str):
    print("Generating VitePress Configuration, Theme, Home Page, and Index...")
    vp_dir = os.path.join(docs_dir, ".vitepress")
    theme_dir = os.path.join(vp_dir, "theme")
    os.makedirs(theme_dir, exist_ok=True)

    # 1. docs/index.md
    with open(os.path.join(docs_dir, "index.md"), "w") as f:
        f.write("""---
layout: home

hero:
  name: "19-Usage-Billing-Engine"
  text: "Real-Time Metered Billing & Rating Engine"
  tagline: "Idempotent consumption telemetry ingestion, multi-tiered graduated rating, append-only double-entry ledgers, and automated billing cycle invoicing."
  actions:
    - theme: brand
      text: Project Overview
      link: /00a-project-analysis
    - theme: alt
      text: 2-Minute Pitch
      link: /00b-project-pitch
    - theme: alt
      text: System Design
      link: /system-design/
    - theme: alt
      text: Interview Q&A (150+)
      link: /09-interview-qa

features:
  - title: "F1: Usage Event Store"
    details: "Granular metered usage records with multi-dimensional metadata, tenant isolation, and composite unique idempotency constraints."
    link: /features/F1-usage-event-store
  - title: "F2: Idempotent Ingestion"
    details: "High-throughput ingestion pipeline validating schema formats, clock drift windows, and eliminating duplicate billing retries."
    link: /features/F2-idempotent-ingestion
  - title: "F3: Multi-Tiered Rating Engine"
    details: "Evaluates raw usage against graduated brackets, volume tiers, overages, and flat fees calculated in exact integer cents."
    link: /features/F3-rating-engine
  - title: "F4: Double-Entry Financial Ledger"
    details: "Append-only accounting journal strictly enforcing the fundamental invariant: sum of debits equals sum of credits."
    link: /features/F4-double-entry-ledger
  - title: "F5: Automated Invoicing"
    details: "Locks meter cycles, aggregates line items, applies discounts/taxes, and assigns gapless sequential invoice numbers."
    link: /features/F5-invoicing-engine
  - title: "F6: Payments, Retries & Dunning"
    details: "Two-step authorization/capture, idempotent charge retries, and automated clock-driven dunning workflows."
    link: /features/F6-payments-collections
  - title: "F7: Aggregation & Period Lifecycle"
    details: "Billing period states (OPEN/CLOSING/CLOSED) and differential testing proving pre-aggregates match raw events."
    link: /features/F7-aggregation-periods
  - title: "F8: Subscription Proration"
    details: "Second-exact pro-rata credit and charge calculations using Python Decimal ROUND_HALF_UP arithmetic."
    link: /features/F8-proration-lifecycle
  - title: "F9: Security, RBAC & Audit"
    details: "Deny-by-default role-based access control, SHA-256 API key authentication, and automated PII scrubbing."
    link: /features/F9-security-rbac-audit
  - title: "F10: Customer Billing Console"
    details: "Fast Vanilla JS & CSS dark-mode dashboard displaying live revenue KPIs, invoice explorers, and line item inspectors."
    link: /features/F10-billing-console-frontend
  - title: "18-Chapter System Design Guide"
    details: "Comprehensive financial systems design deep dive modeling 100,000 events/second and multi-terabyte ledger scaling."
    link: /system-design/
  - title: "Master Verification Checklist"
    details: "All 275 verification checklist items thoroughly answered with implementation file paths, tests, and trade-offs."
    link: /13-master-checklist
---
""")

    # 2. docs/README.md
    with open(os.path.join(docs_dir, "README.md"), "w") as f:
        f.write("""# Documentation Index: 19-Usage-Billing-Engine

Welcome to the comprehensive, interview-ready documentation suite for `19-usage-billing-engine`. Below is the complete reading sequence:

---

### Step 0: Pre-Check & Project Analysis
1. [Project Type & Adaptation Track](./00-project-type.md)
2. [Full Project Analysis & Trace](./00a-project-analysis.md)
3. [Project Pitches (30s & 2m)](./00b-project-pitch.md)
4. [Project Structure & Tech Map](./00-project-map.md)

---

### Step 1 & 2: Feature Inventory & Deep Dives
5. [Feature Inventory (All F1 – F10)](./01-features.md)
   - [F1: Usage Event Store](./features/F1-usage-event-store.md)
   - [F2: Idempotent Ingestion Pipeline](./features/F2-idempotent-ingestion.md)
   - [F3: Multi-Tiered Rating Engine](./features/F3-rating-engine.md)
   - [F4: Double-Entry Financial Ledger](./features/F4-double-entry-ledger.md)
   - [F5: Automated Invoicing Engine](./features/F5-invoicing-engine.md)
   - [F6: Payments, Retries & Dunning](./features/F6-payments-collections.md)
   - [F7: Aggregation & Period Lifecycle](./features/F7-aggregation-periods.md)
   - [F8: Subscription Lifecycle & Proration](./features/F8-proration-lifecycle.md)
   - [F9: Security, RBAC & Audit Logging](./features/F9-security-rbac-audit.md)
   - [F10: Customer Billing Console Frontend](./features/F10-billing-console-frontend.md)

---

### Step 3 – 9: Engineering Guides
6. [Step-by-Step Rebuild Order](./02-build-order.md)
7. [Complete REST API Reference](./03-api-reference.md)
8. [Technology Choices & Comparisons](./04-tech-comparisons.md)
9. [Architecture & System Design](./05-architecture.md)
10. [Security & OWASP Top 10 Audit](./06-security.md)
11. [AI & Spend Analytics Architecture](./07-ai-integration.md)
12. [Quality, Testing & Operations](./08-quality-and-ops.md)

---

### Step 10 – 14: Interview Prep, Verification & System Design
13. [Technical Interview Q&A (150+ Questions)](./09-interview-qa.md)
14. [Gaps & Roadmap Improvements](./10-gaps-and-improvements.md)
15. [Technical Glossary](./11-glossary.md)
16. [Developer Confirm List](./12-confirm-list.md)
17. [Master Checklist (All 275 Items)](./13-master-checklist.md)
18. [Say It Out Loud: Spoken Scripts](./14-say-it-out-loud.md)
19. [18-Chapter Financial Systems Design Guide](./system-design/)
20. [Architecture Decision Records (ADR Log)](./system-design/decisions.md)
""")

    # 3. .vitepress/config.mjs
    with open(os.path.join(vp_dir, "config.mjs"), "w") as f:
        f.write("""import { defineConfig } from 'vitepress';
import { withMermaid } from 'vitepress-plugin-mermaid';

export default withMermaid(
  defineConfig({
    title: '19-Usage-Billing-Engine',
    description: 'Enterprise metered billing, mathematical rating, and double-entry financial ledger engine.',
    appearance: 'dark',
    base: '/',
    themeConfig: {
      nav: [
        { text: 'Guide', link: '/00a-project-analysis' },
        { text: 'Features', link: '/01-features' },
        { text: 'API Reference', link: '/03-api-reference' },
        { text: 'Comparisons', link: '/04-tech-comparisons' },
        { text: 'System Design', link: '/system-design/' },
        { text: 'Interview Q&A', link: '/09-interview-qa' },
        { text: 'Checklist (275)', link: '/13-master-checklist' },
        { text: 'Say It Out Loud', link: '/14-say-it-out-loud' }
      ],
      sidebar: [
        {
          text: 'Project Overview',
          collapsed: false,
          items: [
            { text: 'Project Type & Adaptation', link: '/00-project-type' },
            { text: 'Full Project Analysis', link: '/00a-project-analysis' },
            { text: 'Project Pitches (30s & 2m)', link: '/00b-project-pitch' },
            { text: 'Project Structure & Map', link: '/00-project-map' }
          ]
        },
        {
          text: 'Feature Deep Dives',
          collapsed: false,
          items: [
            { text: 'Feature Inventory (All)', link: '/01-features' },
            { text: 'F1: Usage Event Store', link: '/features/F1-usage-event-store' },
            { text: 'F2: Idempotent Ingestion', link: '/features/F2-idempotent-ingestion' },
            { text: 'F3: Multi-Tiered Rating', link: '/features/F3-rating-engine' },
            { text: 'F4: Double-Entry Ledger', link: '/features/F4-double-entry-ledger' },
            { text: 'F5: Invoicing Engine', link: '/features/F5-invoicing-engine' },
            { text: 'F6: Payments & Dunning', link: '/features/F6-payments-collections' },
            { text: 'F7: Aggregation & Periods', link: '/features/F7-aggregation-periods' },
            { text: 'F8: Subscription Proration', link: '/features/F8-proration-lifecycle' },
            { text: 'F9: Security & Audit', link: '/features/F9-security-rbac-audit' },
            { text: 'F10: Billing Console UI', link: '/features/F10-billing-console-frontend' }
          ]
        },
        {
          text: 'Technical Specifications',
          collapsed: false,
          items: [
            { text: 'Step-by-Step Build Order', link: '/02-build-order' },
            { text: 'Complete API Reference', link: '/03-api-reference' },
            { text: 'Technology Comparisons', link: '/04-tech-comparisons' },
            { text: 'Architecture & Scaling', link: '/05-architecture' },
            { text: 'Security Audit & OWASP', link: '/06-security' },
            { text: 'AI & Spend Forecasting', link: '/07-ai-integration' },
            { text: 'Quality, Testing & Ops', link: '/08-quality-and-ops' }
          ]
        },
        {
          text: 'Financial Systems Design',
          collapsed: false,
          items: [
            { text: 'System Design Overview', link: '/system-design/' },
            { text: '14.1 Capacity Estimation', link: '/system-design/14.1-requirements-and-estimation' },
            { text: '14.2 Architecture Styles', link: '/system-design/14.2-architecture-styles' },
            { text: '14.3 Networking & Protocols', link: '/system-design/14.3-networking-and-communication' },
            { text: '14.4 Load Balancing & Scaling', link: '/system-design/14.4-load-balancing-and-scaling' },
            { text: '14.5 Databases & Storage', link: '/system-design/14.5-databases-and-storage' },
            { text: '14.6 Caching & Idempotency', link: '/system-design/14.6-caching' },
            { text: '14.7 Messaging & Streams', link: '/system-design/14.7-messaging-and-queues' },
            { text: '14.8 Concurrency & Locking', link: '/system-design/14.8-consistency-and-concurrency' },
            { text: '14.9 Resilience & Audits', link: '/system-design/14.9-reliability-and-resilience' },
            { text: '14.10 API & Rate Limiting', link: '/system-design/14.10-api-design-and-rate-limiting' },
            { text: '14.11 Security & SOX', link: '/system-design/14.11-security-architecture' },
            { text: '14.12 Search & AI Design', link: '/system-design/14.12-search-and-ai-architecture' },
            { text: '14.13 Real-Time Telemetry', link: '/system-design/14.13-real-time-systems' },
            { text: '14.14 Observability & Ops', link: '/system-design/14.14-observability-and-operations' },
            { text: '14.15 Performance & Cents', link: '/system-design/14.15-performance-engineering' },
            { text: '14.16 Cost & Trade-offs', link: '/system-design/14.16-cost-and-trade-offs' },
            { text: '14.17 Classic System Design', link: '/system-design/14.17-classic-system-design' },
            { text: 'Architecture Decisions (ADR)', link: '/system-design/decisions' }
          ]
        },
        {
          text: 'Interview Mastery & Quality',
          collapsed: false,
          items: [
            { text: 'Interview Q&A (150+)', link: '/09-interview-qa' },
            { text: 'Gaps & Roadmap', link: '/10-gaps-and-improvements' },
            { text: 'Technical Glossary', link: '/11-glossary' },
            { text: 'Developer Confirm List', link: '/12-confirm-list' },
            { text: 'Master Checklist (275 Items)', link: '/13-master-checklist' },
            { text: 'Say It Out Loud: Rehearsal', link: '/14-say-it-out-loud' }
          ]
        }
      ],
      search: {
        provider: 'local'
      },
      outline: [2, 3]
    },
    mermaid: {
      theme: 'dark'
    },
    vite: {
      optimizeDeps: {
        include: ['mermaid', 'fastdom', 'fastdom/extensions/fastdom-promised.js']
      },
      ssr: {
        noExternal: ['mermaid', 'vitepress-plugin-mermaid', 'fastdom']
      }
    }
  })
);
""")

    # 4. .vitepress/theme/index.js
    with open(os.path.join(theme_dir, "index.js"), "w") as f:
        f.write("""import DefaultTheme from 'vitepress/theme';
import './custom.css';

export default {
  ...DefaultTheme
};
""")

    # 5. .vitepress/theme/custom.css (Pure black dark mode, contrast styling)
    with open(os.path.join(theme_dir, "custom.css"), "w") as f:
        f.write(""":root {
  --vp-c-brand: #6366f1;
  --vp-c-brand-light: #818cf8;
  --vp-c-brand-dark: #4f46e5;
}

.dark {
  --vp-c-bg: #000000 !important;
  --vp-c-bg-alt: #000000 !important;
  --vp-c-bg-elv: #0a0a0a !important;
  --vp-c-bg-soft: #0a0a0a !important;
  --vp-sidebar-bg-color: #000000 !important;
  --vp-c-border: #222222 !important;
  --vp-c-divider: #222222 !important;
  --vp-nav-bg-color: #000000 !important;
}

html.dark body {
  background-color: #000000 !important;
  color: #f1f5f9;
}

/* Enhanced table contrast */
table {
  width: 100%;
  border-collapse: collapse;
  margin: 1.5rem 0;
}

th, td {
  border: 1px solid #222222;
  padding: 10px 14px;
}

th {
  background-color: #0a0a0a;
}
""")

    print("VitePress configuration generated successfully.")
