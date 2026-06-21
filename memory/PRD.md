# Practora — Product Requirements Document

## Original Problem Statement
SaaS booking platform for independent professionals (astrologers, doctors, therapists, dieticians, coaches, yoga teachers, tutors, consultants). NOT a marketplace — every pro gets their own URL like `practora.in/dr-anjali`. Business model: ₹99 first month → ₹499/month, 5% platform fee on bookings.

## Architecture
- **Stack**: FastAPI + MongoDB + React (substituted from spec's Spring Boot + PostgreSQL — functionally equivalent)
- **Auth**: JWT via httpOnly cookie, 7-day expiry
- **Email**: Resend (abstracted — falls back to console logging when no API key)
- **Scheduler**: asyncio background task, 60s tick (reminders + auto-completion)
- **Customer access (no signup)**: per-booking `customer_access_token` magic link

## User Personas
- **Professional**: signs up, picks slug, defines services/availability, manages bookings
- **Customer**: discovers via shared link, books in 3 steps, manages via emailed magic link
- **Admin**: future Phase 4

## Implemented (as of 2026-06-21)

### Phase 1 — Booking MVP
- Marketing landing page (warm beige + terracotta + cocoa palette, Cormorant Garamond + Manrope)
- Pro signup with custom URL slug + live availability check
- JWT auth (login, register, /me, logout)
- Services CRUD (name, description, duration, price, cover image)
- Availability (weekday hours, buffer time, blocked dates)
- Public booking page `/:slug` (service → date → slot → form)
- Booking confirmation page
- Pro dashboard (revenue, upcoming, total bookings, repeat clients) + quick actions
- Seeded demos: `/dr-anjali`, `/astro-raj`

### Phase 2 — Booking Lifecycle (2026-06-21)
- Booking statuses: `CONFIRMED` / `RESCHEDULED` / `CANCELLED` / `COMPLETED` / `NO_SHOW`
- Reschedule flow (customer via magic link + pro via dashboard)
- Cancellation flow (customer + pro), optional reason
- Pro-configurable policies (reschedule window, cancel window, reschedule limit)
- Pro-side no-show marking
- Magic-link customer access — valid until `start_time`
- Email infrastructure via Resend (5 templates: confirmed-customer, confirmed-pro, rescheduled, cancelled, reminder); console fallback when no key
- Reminder scheduler: 24h + 1h before session, to both pro and customer; idempotent flags
- Auto-completion: 30min after `end_time` → status `COMPLETED`
- Booking audit trail (`booking_activities` collection) — immutable, newest-first, with actor_type + metadata
- Frontend: Policies page, Booking Detail page (pro), Manage Booking page (customer), status filter pills

## Prioritized Backlog (Phase 3+)

### P0 — Monetization (Slice A)
- Razorpay subscription: ₹99 first month → ₹499/mo for professionals
- Razorpay booking payments: customer pays at booking (5% platform fee)
- Payment status independent from booking lifecycle (`payment_status` field already exists)

### P1 — Trust & Conversion (Slice C)
- Reviews (1–5 stars + text) with verified-booking gate, displayed on `/:slug`
- Custom intake forms (text, dropdown, file upload) per pro/service

### P2 — Polish (Slice E)
- Object storage for profile photos + service images + intake file uploads (S3 or similar)
- SEO/OG tags on `/:slug` for premium WhatsApp/Insta link previews
- Customer accounts (optional, with booking history)
- Timezone handling (currently IST-only)

### P3 — Admin (Slice D)
- Admin dashboard: users, bookings, payments, subscriptions, platform revenue ledger

## Test Credentials
See `/app/memory/test_credentials.md`.
