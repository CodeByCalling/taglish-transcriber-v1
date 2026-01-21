# Multi‑Tenancy Design Patterns for Taglish Meeting Transcriber

## Current State vs. Target State

**Current (Single‑Tenant)**
- One shared Firestore database
- One Cloud Run instance
- No user authentication
- Direct file access
- Simple password protection

**Target (Multi‑Tenant SaaS)**
- Isolated data per subscriber
- Auto‑scaling infrastructure
- User authentication & authorization
- Subscription billing & limits
- Admin dashboard
- API rate limiting

---

## 1. Multi‑Tenancy Design Patterns

### Option A: Shared Database with Tenant Isolation (Recommended)
**Firestore Structure**:
```
/organizations/{org_id}
  /users/{user_id}
  /transcripts/{transcript_id}
  /subscriptions/{subscription_id}
  /usage_metrics/{month}
```
**Security Rules** enforce that users can only read/write data belonging to their organization.

**Pros**
- Cost‑efficient (single database)
- Easy cross‑tenant analytics
- Simple to manage at scale
- Google‑recommended pattern for Firestore

**Cons**
- Requires careful security‑rule design
- Potential risk of data leakage if mis‑configured

### Option B: Database Per Tenant (Enterprise)
**Architecture**: Each subscriber gets a dedicated Firestore database and Storage bucket.

**Pros**
- Maximum security isolation
- Easy to migrate customers
- Custom performance tuning per tenant

**Cons**
- Higher cost ($1‑$5/month per tenant)
- Complex management at large scale
- Overkill for most use‑cases

**Recommendation**: Use **Option A** for up to 50 000‑100 000 subscribers, and consider a hybrid approach for enterprise customers.

---

## 2. Google Cloud Architecture for Scale
```
┌─────────────────────────────────────┐
│ Front‑end (Firebase Hosting)        │
│   – React/Next.js SPA               │
│   – CDN cached globally             │
└─────────────────────┬───────────────┘
                      │
┌─────────────────────▼───────────────┐
│ Authentication (Firebase Auth)      │
│   – Email/Password, Google, Phone   │
│   – PH‑specific SMS OTP            │
└─────────────────────┬───────────────┘
                      │
┌─────────────────────▼───────────────┐
│ API Layer (Cloud Run)               │
│   – Auto‑scales 0 → 1000+ instances│
│   – Scale‑to‑zero when idle        │
└───────┬───────┬───────┬───────┬─────┘
        │       │       │       │
   Firestore  Storage  Pub/Sub  Cloud Tasks
```

### Key Services
- **Cloud Run** – serverless compute, auto‑scales, per‑request pricing.
- **Cloud Tasks** – reliable job queue, rate limiting, retries.
- **Firestore** – multi‑tenant NoSQL, 10 000 writes/sec, easy security rules.
- **Firebase Storage** – unlimited blob storage, lifecycle rules for auto‑deletion.

---

## 3. Subscription & Billing (Stripe)
- Supports GCash, GrabPay, Maya (PH payment methods).
- Example tiers: Starter (₱499/mo), Professional (₱1 999/mo), Organization (₱7 999/mo).
- Usage tracking stored in `/organizations/{org_id}/usage/{month}` and enforced before processing.

---

## 4. Philippine Market Optimisation
- Deploy to `asia‑southeast1` (Singapore) – ~20‑30 ms latency from Manila.
- Localised UI (English + Tagalog) and currency display in ₱.
- Support for local SMS OTP providers.

---

## 5. Cost & Scaling Estimates (10 000 subscribers)
| Service | Monthly Cost |
|---------|--------------|
| Whisper API (150 k hrs) | $54 000 |
| Cloud Run | $2 500 |
| Firestore | $500 |
| Storage (7‑day) | $450 |
| Cloud Tasks | $50 |
| **Total Infra** | **≈ $57 500** |

Revenue (average ₱1 500 ≈ $27) → $270 000 → **79 % gross margin**.

---

## 6. Security & Compliance (Philippine DPA)
- Data stored in Singapore (acceptable under DPA).
- Encryption at rest (Google default).
- Full delete‑your‑data endpoint.
- Audit logs collection in `/audit_logs/{org_id}/{log_id}`.

---

## 7. Migration Roadmap
1. **Phase 1** – Add Firebase Auth, organization data model, Cloud Tasks.
2. **Phase 2** – Stripe integration, usage limits, admin dashboard.
3. **Phase 3** – Load‑testing, PH payment method validation.
4. **Phase 4** – Public launch, marketing, scaling to 1 000 + users.

---

## 8. Advantages of Google Cloud for the PH Market
- Auto‑scaling, pay‑as‑you‑grow.
- 99.95 % SLA.
- Global CDN for fast UI.
- Tight integration with Firebase services.
- Future Vertex AI custom Taglish models.

---

*Prepared for review – the AI post‑processing implementation plan is stored separately.*
