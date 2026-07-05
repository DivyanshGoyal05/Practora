import React, { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { CreditCard, ShieldCheck, Clock, AlertCircle, CheckCircle2, IndianRupee, Ban, XCircle, Loader2 } from "lucide-react";

const STATUS_META = {
  trial:            { label: "Free trial",   tone: "amber",   icon: Clock },
  none:             { label: "No subscription", tone: "gray",  icon: AlertCircle },
  created:          { label: "Created — awaiting payment", tone: "amber", icon: Clock },
  authenticated:    { label: "Authenticated — waiting for first charge", tone: "blue", icon: Clock },
  active:           { label: "Active", tone: "green", icon: CheckCircle2 },
  pending:          { label: "Payment pending", tone: "amber", icon: AlertCircle },
  halted:           { label: "Halted — payment failed", tone: "red", icon: XCircle },
  cancelled:        { label: "Cancelled", tone: "red", icon: Ban },
  completed:        { label: "Completed", tone: "gray", icon: CheckCircle2 },
  expired:          { label: "Expired", tone: "red", icon: XCircle },
  paused:           { label: "Paused", tone: "gray", icon: Clock },
};

const TONE_CLASS = {
  green: "bg-emerald-50 text-emerald-700 border-emerald-200",
  amber: "bg-amber-50 text-amber-700 border-amber-200",
  red:   "bg-rose-50 text-rose-700 border-rose-200",
  blue:  "bg-sky-50 text-sky-700 border-sky-200",
  gray:  "bg-secondary text-cocoaSoft border-border",
};

function StatusBadge({ status }) {
  const meta = STATUS_META[status] || STATUS_META.none;
  const Icon = meta.icon;
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs uppercase tracking-[0.14em] px-2.5 py-1 rounded-full border ${TONE_CLASS[meta.tone]}`}
      data-testid="subscription-status-badge"
    >
      <Icon className="h-3 w-3" /> {meta.label}
    </span>
  );
}

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
  } catch { return iso; }
}
function fmtDateTime(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch { return iso; }
}

export default function Billing() {
  const { user, refresh } = useAuth();
  const [sub, setSub] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get("/me/subscription");
      setSub(data);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const openCheckout = (result) => {
    if (!window.Razorpay) {
      toast.error("Payment library failed to load. Please refresh.");
      return;
    }
    const options = {
      key: result.key_id,
      subscription_id: result.subscription_id,
      name: "Practora",
      description: `Professional Plan — \u20B9${result.amount_inr}/month`,
      image: "",
      prefill: {
        name: user?.name || "",
        email: user?.email || "",
      },
      theme: { color: "#C86B53" },
      handler: async () => {
        toast.success("Payment authorised — activation may take a few seconds.");
        await refresh();
        await load();
      },
      modal: {
        ondismiss: async () => { await load(); },
      },
    };
    const rp = new window.Razorpay(options);
    rp.on("payment.failed", (resp) => {
      toast.error(resp?.error?.description || "Payment failed");
    });
    rp.open();
  };

  const startSubscription = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/me/subscription/create");
      openCheckout(data);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    } finally { setBusy(false); }
  };

  const cancelSubscription = async () => {
    if (!window.confirm("Cancel your subscription? You'll keep access until the end of the current billing period.")) return;
    setBusy(true);
    try {
      await api.post("/me/subscription/cancel");
      toast.success("Subscription set to cancel at end of period.");
      await refresh();
      await load();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    } finally { setBusy(false); }
  };

  if (loading) return <div className="text-cocoaSoft">Loading…</div>;

  const amountInr = sub?.subscription_amount_inr || sub?.platform_amount_inr || 500;
  const rzpConfigured = sub?.razorpay_configured;
  const status = sub?.subscription_status || "none";
  const hasAccess = sub?.has_access;
  const isTrial = sub?.reason === "trial";
  const canSubscribe = !["active", "authenticated", "pending"].includes(status);
  const canCancel = ["active", "authenticated", "pending"].includes(status);

  return (
    <div className="space-y-8 animate-fade-up max-w-4xl" data-testid="billing-page">
      <div>
        <h1 className="font-heading text-4xl">Billing</h1>
        <p className="text-cocoaSoft mt-1">Your Practora Professional subscription.</p>
      </div>

      {/* Access banner */}
      {!hasAccess && (
        <div className="paper-card p-5 border-rose-200 bg-rose-50 text-rose-800" data-testid="no-access-banner">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 mt-0.5" />
            <div>
              <p className="font-medium">Your booking page is currently unavailable to customers.</p>
              <p className="text-sm mt-1">Subscribe below to reactivate your public page and accept new bookings.</p>
            </div>
          </div>
        </div>
      )}

      {/* Plan card */}
      <div className="paper-card p-6" data-testid="plan-card">
        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
          <div>
            <p className="text-xs tracking-[0.18em] uppercase text-cocoaSoft">Current plan</p>
            <div className="flex items-center gap-3 mt-2">
              <p className="font-heading text-3xl">Professional</p>
              <StatusBadge status={status} />
            </div>
            <p className="text-cocoaSoft text-sm mt-2">
              Full access to your booking page, services, availability, intake forms, reminders and reports.
            </p>
          </div>
          <div className="text-right">
            <p className="font-heading text-5xl flex items-center justify-end"><IndianRupee className="h-8 w-8" />{amountInr}</p>
            <p className="text-xs text-cocoaSoft mt-1 uppercase tracking-[0.15em]">per month, billed automatically</p>
          </div>
        </div>

        <div className="grid md:grid-cols-3 gap-4 mt-6 pt-6 border-t border-border text-sm">
          <div>
            <p className="text-xs uppercase tracking-[0.14em] text-cocoaSoft">Trial ends</p>
            <p className="mt-1 font-medium">{isTrial ? fmtDate(sub?.trial_ends_at) : "—"}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.14em] text-cocoaSoft">Next charge</p>
            <p className="mt-1 font-medium">{fmtDate(sub?.subscription_charge_at)}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.14em] text-cocoaSoft">Current period ends</p>
            <p className="mt-1 font-medium">{fmtDate(sub?.subscription_current_end)}</p>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap gap-3">
          {canSubscribe && (
            <Button onClick={startSubscription} disabled={busy || !rzpConfigured} className="rounded-full btn-lift" data-testid="start-subscription-button">
              {busy ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <CreditCard className="h-4 w-4 mr-2" />}
              Subscribe for ₹{amountInr}/month
            </Button>
          )}
          {canCancel && (
            <Button variant="outline" onClick={cancelSubscription} disabled={busy} data-testid="cancel-subscription-button">
              {busy ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Ban className="h-4 w-4 mr-2" />}
              Cancel subscription
            </Button>
          )}
          {sub?.cancel_at_cycle_end && (
            <span className="text-sm text-cocoaSoft self-center">Will end on {fmtDate(sub?.subscription_current_end)}</span>
          )}
        </div>

        {!rzpConfigured && (
          <div className="mt-4 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-3" data-testid="razorpay-not-configured-notice">
            Payments are not configured yet on this server. Once the admin adds Razorpay keys, you’ll be able to subscribe.
          </div>
        )}
      </div>

      {/* Trust box */}
      <div className="paper-card p-5 flex items-start gap-3" data-testid="security-note">
        <ShieldCheck className="h-5 w-5 text-primary shrink-0 mt-0.5" />
        <p className="text-sm text-cocoaSoft">
          Payments are processed securely by <span className="font-medium text-foreground">Razorpay</span>. Practora never stores your card details. Your subscription auto-renews monthly and can be cancelled anytime — access continues until the end of the paid period.
        </p>
      </div>

      {/* Recent events */}
      {(sub?.recent_events || []).length > 0 && (
        <div>
          <h2 className="font-heading text-2xl mb-3">Activity</h2>
          <div className="paper-card divide-y divide-border" data-testid="subscription-events-list">
            {sub.recent_events.map((ev) => (
              <div key={ev.id} className="p-4 flex items-center justify-between text-sm">
                <div>
                  <p className="font-medium">{ev.event_type}</p>
                  {ev.subscription_id && <p className="text-xs text-cocoaSoft">{ev.subscription_id}</p>}
                </div>
                <span className="text-cocoaSoft text-xs">{fmtDateTime(ev.created_at)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
