import { defineConfig } from 'vitepress';
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
