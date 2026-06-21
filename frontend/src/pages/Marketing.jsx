import React from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ArrowRight, Calendar, Sparkles, Globe, ShieldCheck, Clock, Quote } from "lucide-react";

const features = [
  { icon: Globe, title: "Your own booking URL", body: "practora.in/your-name — share it on WhatsApp, Insta bio, or your site." },
  { icon: Calendar, title: "Smart scheduling", body: "Weekday/weekend hours, blocked dates, buffer time. Slots generate automatically." },
  { icon: ShieldCheck, title: "Built for trust", body: "A premium booking page that reflects the quality of your practice." },
  { icon: Clock, title: "Set up in minutes", body: "From signup to first booking in under 10 minutes. No setup calls. No code." },
];

const categories = ["Astrologers", "Doctors", "Therapists", "Dieticians", "Coaches", "Yoga Teachers", "Tutors", "Consultants"];

export default function Marketing() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Nav */}
      <header className="glass-nav sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2" data-testid="logo-link">
            <div className="h-8 w-8 rounded-full bg-primary text-primary-foreground grid place-items-center font-heading text-lg">P</div>
            <span className="font-heading text-2xl tracking-tight">Practora</span>
          </Link>
          <nav className="hidden md:flex items-center gap-8 text-sm">
            <a href="#how" className="text-cocoaSoft hover:text-foreground transition-colors">How it works</a>
            <a href="#features" className="text-cocoaSoft hover:text-foreground transition-colors">Features</a>
            <a href="#pricing" className="text-cocoaSoft hover:text-foreground transition-colors">Pricing</a>
            <a href="/dr-anjali" target="_blank" rel="noreferrer" className="text-cocoaSoft hover:text-foreground transition-colors">See example</a>
          </nav>
          <div className="flex items-center gap-2">
            <Link to="/login" data-testid="nav-login-link">
              <Button variant="ghost" size="sm">Sign in</Button>
            </Link>
            <Link to="/signup" data-testid="nav-signup-link">
              <Button size="sm" className="rounded-full btn-lift">Start free</Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero — Tetris asymmetric */}
      <section className="relative max-w-7xl mx-auto px-6 pt-16 md:pt-24 pb-20">
        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-12 md:col-span-7 flex flex-col justify-center">
            <span className="text-xs tracking-[0.18em] uppercase text-cocoaSoft mb-6" data-testid="hero-eyebrow">
              For independent professionals
            </span>
            <h1 className="font-heading text-5xl md:text-6xl lg:text-7xl leading-[1.02] tracking-tight text-foreground" data-testid="hero-title">
              Your practice,<br/>
              <span className="italic text-primary">beautifully booked.</span>
            </h1>
            <p className="mt-6 text-lg text-cocoaSoft max-w-xl leading-relaxed" data-testid="hero-subtitle">
              Practora gives astrologers, doctors, therapists, dieticians and coaches a premium booking page —
              their own URL, smart scheduling, and effortless consultations. No marketplace. Just you, your clients, and a calmer business.
            </p>
            <div className="mt-9 flex flex-wrap gap-3 items-center">
              <Link to="/signup" data-testid="hero-cta-signup">
                <Button size="lg" className="rounded-full btn-lift px-7">
                  Claim your URL <ArrowRight className="h-4 w-4 ml-2" />
                </Button>
              </Link>
              <a href="/dr-anjali" target="_blank" rel="noreferrer" data-testid="hero-cta-demo">
                <Button size="lg" variant="outline" className="rounded-full border-cocoa/20 hover:bg-secondary">
                  See a live page
                </Button>
              </a>
            </div>
            <div className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-xs text-cocoaSoft">
              <span>✓ ₹99 first month</span>
              <span>✓ Cancel anytime</span>
              <span>✓ Set up in 10 minutes</span>
            </div>
          </div>

          <div className="col-span-12 md:col-span-5">
            <div className="grid grid-cols-6 gap-3 h-full">
              <div className="col-span-6 row-span-2 relative overflow-hidden rounded-2xl border border-border min-h-[280px]">
                <img
                  src="https://images.pexels.com/photos/4100671/pexels-photo-4100671.jpeg"
                  alt="Professional"
                  className="w-full h-full object-cover"
                />
                <div className="absolute bottom-3 left-3 right-3 bg-white/90 backdrop-blur rounded-xl p-3 border border-border">
                  <p className="text-xs uppercase tracking-[0.15em] text-cocoaSoft">Live page</p>
                  <p className="text-sm font-medium mt-0.5">practora.in/dr-anjali</p>
                </div>
              </div>
              <div className="col-span-3 paper-card p-4 grain relative overflow-hidden">
                <Sparkles className="h-5 w-5 text-primary" />
                <p className="font-heading text-2xl mt-2 leading-tight">99<span className="text-base align-top">₹</span></p>
                <p className="text-xs text-cocoaSoft mt-1">first month</p>
              </div>
              <div className="col-span-3 paper-card p-4">
                <p className="text-xs uppercase tracking-[0.15em] text-cocoaSoft">Next session</p>
                <p className="font-heading text-xl mt-2 leading-tight">Today, 4:30 PM</p>
                <p className="text-xs text-cocoaSoft mt-1">Therapy with Maya</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Built for ribbon */}
      <section className="border-y border-border bg-beigeMuted/50">
        <div className="max-w-7xl mx-auto px-6 py-6 flex flex-wrap items-center gap-x-10 gap-y-3 text-sm text-cocoaSoft">
          <span className="text-xs tracking-[0.18em] uppercase text-foreground">Built for</span>
          {categories.map((c) => (
            <span key={c} className="hover:text-primary transition-colors">{c}</span>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="max-w-7xl mx-auto px-6 py-24">
        <div className="grid grid-cols-12 gap-8">
          <div className="col-span-12 md:col-span-4">
            <span className="text-xs tracking-[0.18em] uppercase text-cocoaSoft">How it works</span>
            <h2 className="font-heading text-4xl md:text-5xl mt-3 leading-tight">Three steps. <br/><em className="text-primary not-italic font-light">No friction.</em></h2>
          </div>
          <div className="col-span-12 md:col-span-8 grid sm:grid-cols-3 gap-4">
            {[
              { n: "01", t: "Claim your URL", d: "Pick something memorable like /dr-anjali or /yoga-priya." },
              { n: "02", t: "Add services + hours", d: "Set prices, durations and when you're available." },
              { n: "03", t: "Share & get booked", d: "Drop the link in your bio. Clients book themselves." },
            ].map((s) => (
              <div key={s.n} className="paper-card p-6">
                <p className="font-heading text-3xl text-primary">{s.n}</p>
                <p className="font-medium mt-4">{s.t}</p>
                <p className="text-sm text-cocoaSoft mt-2 leading-relaxed">{s.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="max-w-7xl mx-auto px-6 py-24 border-t border-border">
        <div className="max-w-2xl">
          <span className="text-xs tracking-[0.18em] uppercase text-cocoaSoft">Why Practora</span>
          <h2 className="font-heading text-4xl md:text-5xl mt-3 leading-tight">A booking system that <em className="text-primary not-italic font-light">feels like your practice.</em></h2>
        </div>
        <div className="mt-12 grid grid-cols-1 md:grid-cols-2 gap-6">
          {features.map((f) => (
            <div key={f.title} className="paper-card p-7 flex gap-5">
              <div className="h-10 w-10 rounded-lg bg-primary/10 text-primary grid place-items-center shrink-0">
                <f.icon className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-heading text-2xl leading-tight">{f.title}</h3>
                <p className="text-sm text-cocoaSoft mt-2 leading-relaxed">{f.body}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Testimonial */}
      <section className="max-w-5xl mx-auto px-6 py-24">
        <Quote className="h-10 w-10 text-primary/50" />
        <p className="font-heading text-3xl md:text-4xl mt-6 leading-snug text-foreground">
          "I used to lose hours every week to WhatsApp scheduling. Now my clients just book themselves —
          and the page looks like something I'd actually pay a designer for."
        </p>
        <p className="mt-6 text-sm text-cocoaSoft">— Anjali, clinical psychologist</p>
      </section>

      {/* Pricing */}
      <section id="pricing" className="max-w-7xl mx-auto px-6 py-24 border-t border-border">
        <div className="grid grid-cols-12 gap-8 items-end">
          <div className="col-span-12 md:col-span-6">
            <span className="text-xs tracking-[0.18em] uppercase text-cocoaSoft">Pricing</span>
            <h2 className="font-heading text-4xl md:text-5xl mt-3 leading-tight">One plan. <em className="text-primary not-italic font-light">Honest pricing.</em></h2>
            <p className="mt-4 text-cocoaSoft max-w-md">Start at ₹99 for your first month. Then ₹499/month after that. 5% platform fee on bookings. No setup fees. Cancel anytime.</p>
          </div>
          <div className="col-span-12 md:col-span-6">
            <div className="paper-card p-8 relative overflow-hidden">
              <div className="absolute -top-10 -right-10 h-40 w-40 bg-accent/30 rounded-full blur-3xl" />
              <p className="text-xs tracking-[0.18em] uppercase text-cocoaSoft">Practora Pro</p>
              <div className="flex items-baseline gap-2 mt-3">
                <span className="font-heading text-6xl">₹99</span>
                <span className="text-cocoaSoft text-sm">first month</span>
              </div>
              <p className="text-sm text-cocoaSoft mt-1">then ₹499 / month + 5% per booking</p>
              <ul className="mt-6 space-y-2 text-sm">
                {["Your own booking URL","Unlimited services & bookings","Smart availability","Customer notifications","Cancel anytime"].map((it) => (
                  <li key={it} className="flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-primary" /> {it}</li>
                ))}
              </ul>
              <Link to="/signup" data-testid="pricing-cta-signup">
                <Button size="lg" className="rounded-full mt-8 w-full btn-lift">Start now for ₹99</Button>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border">
        <div className="max-w-7xl mx-auto px-6 py-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 text-sm text-cocoaSoft">
          <div className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-full bg-primary text-primary-foreground grid place-items-center font-heading">P</div>
            <span className="font-heading text-lg text-foreground">Practora</span>
          </div>
          <p>© {new Date().getFullYear()} Practora. Built for the independent practitioner.</p>
        </div>
      </footer>
    </div>
  );
}
