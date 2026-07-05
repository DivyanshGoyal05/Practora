import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { formatApiError } from "@/lib/api";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const u = await login(email, password);
      toast.success("Welcome back");
      nav(u?.role === "admin" ? "/admin" : "/dashboard");
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <div className="hidden lg:block relative bg-beigeMuted">
        <img
          src="https://images.pexels.com/photos/14797769/pexels-photo-14797769.jpeg"
          alt=""
          className="w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-cocoa/20" />
        <div className="absolute bottom-10 left-10 right-10 text-white">
          <p className="font-heading text-4xl leading-tight">Welcome back to your practice.</p>
        </div>
      </div>

      <div className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <Link to="/" className="flex items-center gap-2 mb-10" data-testid="logo-link">
            <div className="h-8 w-8 rounded-full bg-primary text-primary-foreground grid place-items-center font-heading text-lg">P</div>
            <span className="font-heading text-2xl">Practora</span>
          </Link>

          <h1 className="font-heading text-4xl">Sign in</h1>
          <p className="text-cocoaSoft mt-2">Welcome back. Continue managing your practice.</p>

          <form onSubmit={submit} className="mt-8 space-y-5" data-testid="login-form">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@practice.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                data-testid="login-email-input"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                data-testid="login-password-input"
              />
            </div>
            <Button type="submit" disabled={submitting} className="w-full rounded-full btn-lift" data-testid="login-submit-button">
              {submitting ? "Signing in…" : "Sign in"}
            </Button>
          </form>

          <p className="mt-6 text-sm text-cocoaSoft">
            New here?{" "}
            <Link to="/signup" className="text-primary hover:underline" data-testid="signup-link">
              Create your booking page →
            </Link>
          </p>

          <div className="mt-10 paper-card p-4 text-xs text-cocoaSoft">
            <p className="font-medium text-foreground mb-1">Try a demo account</p>
            <p>anjali@practora.in / demo123 — or — raj@practora.in / demo123</p>
          </div>
        </div>
      </div>
    </div>
  );
}
