import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import api, { formatApiError } from "@/lib/api";
import { Check, X } from "lucide-react";

const CATEGORIES = ["Astrologer", "Doctor", "Therapist", "Dietician", "Coach", "Yoga Teacher", "Tutor", "Consultant"];

export default function Signup() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "", slug: "", category: "Therapist" });
  const [submitting, setSubmitting] = useState(false);
  const [slugStatus, setSlugStatus] = useState(null); // null | 'ok' | 'taken' | 'checking'
  const [pricing, setPricing] = useState({ subscription_amount_inr: 500, trial_days: 7 });

  const setField = (k) => (e) => setForm((p) => ({ ...p, [k]: e.target?.value ?? e }));

  useEffect(() => {
    api.get("/settings/public")
      .then((r) => setPricing({
        subscription_amount_inr: r.data.subscription_amount_inr ?? 500,
        trial_days: r.data.trial_days ?? 7,
      }))
      .catch(() => {});
  }, []);

  // Live slug availability
  useEffect(() => {
    const s = form.slug.trim();
    if (!s || s.length < 3) { setSlugStatus(null); return; }
    setSlugStatus("checking");
    const t = setTimeout(async () => {
      try {
        const { data } = await api.get("/me/slug-available", { params: { slug: s } });
        setSlugStatus(data.available ? "ok" : "taken");
      } catch { setSlugStatus(null); }
    }, 350);
    return () => clearTimeout(t);
  }, [form.slug]);

  const slugClean = form.slug.toLowerCase().replace(/[^a-z0-9-]/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");

  const submit = async (e) => {
    e.preventDefault();
    if (slugStatus === "taken") {
      toast.error("That URL is taken — try another");
      return;
    }
    setSubmitting(true);
    try {
      await register({ ...form, slug: slugClean });
      toast.success("Welcome to Practora");
      nav("/dashboard");
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Could not create account");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <div className="hidden lg:block relative bg-beigeMuted">
        <img src="https://images.pexels.com/photos/26268159/pexels-photo-26268159.jpeg" alt="" className="w-full h-full object-cover" />
        <div className="absolute inset-0 bg-cocoa/25" />
        <div className="absolute bottom-10 left-10 right-10 text-white">
          <p className="font-heading text-4xl leading-tight">Your booking page,<br/><em>ready in minutes.</em></p>
          <p className="text-sm mt-3 opacity-80">Join astrologers, doctors, therapists, and coaches building calmer businesses.</p>
        </div>
      </div>

      <div className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <Link to="/" className="flex items-center gap-2 mb-8" data-testid="logo-link">
            <div className="h-8 w-8 rounded-full bg-primary text-primary-foreground grid place-items-center font-heading text-lg">P</div>
            <span className="font-heading text-2xl">Practora</span>
          </Link>
          <h1 className="font-heading text-4xl">Claim your URL</h1>
          <p className="text-cocoaSoft mt-2">
            {pricing.trial_days > 0
              ? `${pricing.trial_days}-day free trial, then ₹${pricing.subscription_amount_inr}/month. No commission on bookings.`
              : `₹${pricing.subscription_amount_inr}/month. No commission on bookings.`}
          </p>

          <form onSubmit={submit} className="mt-8 space-y-5" data-testid="signup-form">
            <div className="space-y-2">
              <Label htmlFor="name">Your name</Label>
              <Input id="name" placeholder="Dr. Anjali Mehta" value={form.name} onChange={setField("name")} required data-testid="signup-name-input" />
            </div>

            <div className="space-y-2">
              <Label htmlFor="slug">Booking URL</Label>
              <div className="flex items-stretch border border-border rounded-md overflow-hidden bg-white focus-within:ring-2 focus-within:ring-primary">
                <span className="px-3 grid place-items-center text-sm text-cocoaSoft bg-secondary">practora.in/</span>
                <input
                  id="slug"
                  className="flex-1 px-3 py-2 text-sm outline-none"
                  placeholder="your-name"
                  value={form.slug}
                  onChange={setField("slug")}
                  required
                  data-testid="signup-slug-input"
                />
                <span className="px-3 grid place-items-center w-10">
                  {slugStatus === "ok" && <Check className="h-4 w-4 text-green-600" data-testid="slug-available-icon" />}
                  {slugStatus === "taken" && <X className="h-4 w-4 text-destructive" data-testid="slug-taken-icon" />}
                </span>
              </div>
              {slugClean && (
                <p className="text-xs text-cocoaSoft">
                  Your page: <span className="text-foreground">practora.in/{slugClean}</span>
                  {slugStatus === "taken" && <span className="ml-2 text-destructive">— already taken</span>}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label>I am a</Label>
              <Select value={form.category} onValueChange={(v) => setForm((p) => ({ ...p, category: v }))}>
                <SelectTrigger data-testid="signup-category-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {CATEGORIES.map((c) => (
                    <SelectItem key={c} value={c}>{c}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" placeholder="you@practice.com" value={form.email} onChange={setField("email")} required data-testid="signup-email-input" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" placeholder="At least 6 characters" minLength={6} value={form.password} onChange={setField("password")} required data-testid="signup-password-input" />
            </div>

            <Button type="submit" disabled={submitting || slugStatus === "taken"} className="w-full rounded-full btn-lift" data-testid="signup-submit-button">
              {submitting ? "Creating…" : "Create my booking page"}
            </Button>
          </form>

          <p className="mt-6 text-sm text-cocoaSoft">
            Already have an account?{" "}
            <Link to="/login" className="text-primary hover:underline" data-testid="login-link">Sign in →</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
