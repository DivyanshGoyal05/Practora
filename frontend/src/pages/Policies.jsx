import React, { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { Clock, Ban, RotateCw } from "lucide-react";

export default function Policies() {
  const { user, refresh } = useAuth();
  const [policies, setPolicies] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/me/policies").then((r) => setPolicies(r.data));
  }, []);

  if (!policies) return <div className="text-cocoaSoft">Loading…</div>;

  const set = (k) => (e) => setPolicies((p) => ({ ...p, [k]: Number(e.target.value) }));

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.put("/me/policies", policies);
      await refresh();
      toast.success("Policies saved");
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={save} className="space-y-8 animate-fade-up max-w-3xl" data-testid="policies-form">
      <div>
        <h1 className="font-heading text-4xl">Policies</h1>
        <p className="text-cocoaSoft mt-1">Set the rules customers see when they try to change a booking.</p>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="paper-card p-6">
          <RotateCw className="h-5 w-5 text-primary" />
          <h3 className="font-heading text-2xl mt-3">Reschedule window</h3>
          <p className="text-sm text-cocoaSoft mt-1">Customers can self-reschedule up to this many hours before start.</p>
          <div className="mt-4 flex items-center gap-3">
            <Input type="number" min={0} max={720} value={policies.reschedule_window_hours} onChange={set("reschedule_window_hours")} className="w-28" data-testid="policy-reschedule-window-input" />
            <span className="text-sm text-cocoaSoft">hours</span>
          </div>
        </div>

        <div className="paper-card p-6">
          <Ban className="h-5 w-5 text-primary" />
          <h3 className="font-heading text-2xl mt-3">Cancellation window</h3>
          <p className="text-sm text-cocoaSoft mt-1">Customers can self-cancel up to this many hours before start.</p>
          <div className="mt-4 flex items-center gap-3">
            <Input type="number" min={0} max={720} value={policies.cancel_window_hours} onChange={set("cancel_window_hours")} className="w-28" data-testid="policy-cancel-window-input" />
            <span className="text-sm text-cocoaSoft">hours</span>
          </div>
        </div>

        <div className="paper-card p-6 md:col-span-2">
          <Clock className="h-5 w-5 text-primary" />
          <h3 className="font-heading text-2xl mt-3">Reschedule limit</h3>
          <p className="text-sm text-cocoaSoft mt-1">Max times a customer can self-reschedule. You can still reschedule from your dashboard after this.</p>
          <div className="mt-4 flex items-center gap-3">
            <Input type="number" min={0} max={20} value={policies.reschedule_limit} onChange={set("reschedule_limit")} className="w-28" data-testid="policy-reschedule-limit-input" />
            <span className="text-sm text-cocoaSoft">times</span>
          </div>
        </div>
      </div>

      <div className="flex justify-end">
        <Button type="submit" disabled={saving} className="rounded-full btn-lift" data-testid="save-policies-button">
          {saving ? "Saving…" : "Save policies"}
        </Button>
      </div>
    </form>
  );
}
