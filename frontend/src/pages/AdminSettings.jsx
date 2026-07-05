import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Settings2, Users, ShieldAlert } from "lucide-react";

function fmtDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }); }
  catch { return iso; }
}

export default function AdminSettings() {
  const { user, loading } = useAuth();
  const nav = useNavigate();
  const [settings, setSettings] = useState(null);
  const [subs, setSubs] = useState([]);
  const [saving, setSaving] = useState(false);
  const [amount, setAmount] = useState(500);
  const [trialDays, setTrialDays] = useState(7);

  useEffect(() => {
    if (loading) return;
    if (!user || user.role !== "admin") { nav("/login"); return; }
    api.get("/admin/settings").then((r) => {
      setSettings(r.data);
      setAmount(r.data.subscription_amount_inr);
      setTrialDays(r.data.trial_days ?? 7);
    });
    api.get("/admin/subscriptions").then((r) => setSubs(r.data));
  }, [user, loading, nav]);

  if (loading || !settings) return <div className="min-h-screen grid place-items-center text-cocoaSoft">Loading…</div>;

  const save = async (e) => {
    e.preventDefault();
    const nAmt = Number(amount);
    if (!Number.isInteger(nAmt) || nAmt < 1) { toast.error("Enter a valid amount"); return; }
    setSaving(true);
    try {
      const { data } = await api.put("/admin/settings", { subscription_amount_inr: nAmt, trial_days: Number(trialDays) });
      setSettings(data);
      toast.success("Settings saved");
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    } finally { setSaving(false); }
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="glass-nav">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-full bg-primary text-primary-foreground grid place-items-center font-heading">P</div>
            <span className="font-heading text-xl">Practora Admin</span>
          </div>
          <span className="text-xs text-cocoaSoft">{user?.email}</span>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-10 space-y-10">
        <form onSubmit={save} className="space-y-6" data-testid="admin-settings-form">
          <div>
            <h1 className="font-heading text-4xl flex items-center gap-3"><Settings2 className="h-8 w-8 text-primary" /> Platform settings</h1>
            <p className="text-cocoaSoft mt-1">Configure subscription amount and trial period for all professionals.</p>
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            <div className="paper-card p-6">
              <Label className="text-xs uppercase tracking-[0.14em] text-cocoaSoft">Monthly subscription amount (INR)</Label>
              <div className="flex items-center gap-2 mt-3">
                <span className="text-2xl font-heading">₹</span>
                <Input type="number" min={1} max={100000} value={amount} onChange={(e) => setAmount(e.target.value)} className="w-40 text-lg" data-testid="admin-amount-input" />
                <span className="text-sm text-cocoaSoft">/ month</span>
              </div>
              <p className="text-xs text-cocoaSoft mt-3">Changing this creates a new Razorpay plan. Existing subscribers stay on their current plan until they cancel and resubscribe.</p>
            </div>

            <div className="paper-card p-6">
              <Label className="text-xs uppercase tracking-[0.14em] text-cocoaSoft">Free trial (days)</Label>
              <div className="flex items-center gap-2 mt-3">
                <Input type="number" min={0} max={90} value={trialDays} onChange={(e) => setTrialDays(e.target.value)} className="w-24 text-lg" data-testid="admin-trial-days-input" />
                <span className="text-sm text-cocoaSoft">days from signup</span>
              </div>
              <p className="text-xs text-cocoaSoft mt-3">Applies to new sign-ups. Set to 0 to require immediate payment.</p>
            </div>
          </div>

          <div className="paper-card p-4 flex items-center gap-3 text-sm">
            <ShieldAlert className={`h-4 w-4 ${settings.razorpay_configured ? "text-emerald-600" : "text-amber-600"}`} />
            <span>
              Razorpay: <span className="font-medium">{settings.razorpay_configured ? "Configured" : "Not configured"}</span>
              {settings.current_plan_id && (
                <span className="text-cocoaSoft"> · current plan {settings.current_plan_id}</span>
              )}
            </span>
          </div>

          <Button type="submit" disabled={saving} className="rounded-full btn-lift" data-testid="save-admin-settings-button">
            {saving ? "Saving…" : "Save settings"}
          </Button>
        </form>

        <div>
          <h2 className="font-heading text-3xl flex items-center gap-3 mb-4"><Users className="h-6 w-6 text-primary" /> Professionals & subscriptions</h2>
          <div className="paper-card overflow-x-auto" data-testid="admin-subscriptions-table">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-[0.14em] text-cocoaSoft border-b border-border">
                  <th className="p-3">Name</th>
                  <th className="p-3">Email</th>
                  <th className="p-3">Slug</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Trial ends</th>
                  <th className="p-3">Period ends</th>
                  <th className="p-3">Last payment</th>
                </tr>
              </thead>
              <tbody>
                {subs.map((s) => (
                  <tr key={s.id} className="border-b border-border last:border-0" data-testid={`admin-sub-row-${s.id}`}>
                    <td className="p-3 font-medium">{s.name}</td>
                    <td className="p-3 text-cocoaSoft">{s.email}</td>
                    <td className="p-3 text-cocoaSoft">{s.slug || "—"}</td>
                    <td className="p-3"><span className="uppercase text-xs tracking-[0.14em]">{s.subscription_status || "none"}</span></td>
                    <td className="p-3 text-cocoaSoft">{fmtDate(s.trial_ends_at)}</td>
                    <td className="p-3 text-cocoaSoft">{fmtDate(s.subscription_current_end)}</td>
                    <td className="p-3 text-cocoaSoft">{fmtDate(s.subscription_last_payment_at)}</td>
                  </tr>
                ))}
                {subs.length === 0 && (
                  <tr><td colSpan={7} className="p-6 text-center text-cocoaSoft">No professionals yet.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
