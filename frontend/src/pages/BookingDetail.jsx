import React, { useEffect, useMemo, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import api, { formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Calendar } from "@/components/ui/calendar";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import { ArrowLeft, Calendar as CalIcon, Clock, IndianRupee, Mail, Phone, AlertTriangle, History, RotateCw, Ban, UserX } from "lucide-react";

const STATUS_STYLES = {
  CONFIRMED: "bg-green-50 text-green-700 border-green-200",
  RESCHEDULED: "bg-amber-50 text-amber-800 border-amber-200",
  CANCELLED: "bg-rose-50 text-rose-700 border-rose-200",
  COMPLETED: "bg-stone-100 text-stone-700 border-stone-200",
  NO_SHOW: "bg-stone-100 text-stone-700 border-stone-200",
};

function StatusPill({ status }) {
  return (
    <span className={`text-xs uppercase tracking-[0.15em] px-2.5 py-1 rounded-full border ${STATUS_STYLES[status] || ""}`} data-testid={`status-pill-${status}`}>
      {status?.replace("_", " ")}
    </span>
  );
}

const ACTION_LABELS = {
  BOOKING_CREATED: "Booking created",
  BOOKING_CONFIRMED: "Booking confirmed",
  BOOKING_RESCHEDULED: "Booking rescheduled",
  BOOKING_CANCELLED: "Booking cancelled",
  BOOKING_COMPLETED: "Marked completed",
  BOOKING_NO_SHOW: "Marked no-show",
  REMINDER_SENT_24H: "24h reminder sent",
  REMINDER_SENT_1H: "1h reminder sent",
};

export default function BookingDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const [data, setData] = useState(null);
  const [resOpen, setResOpen] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [nsOpen, setNsOpen] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get(`/me/bookings/${id}`);
      setData(data);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Could not load booking");
    }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id]);

  if (!data) return <div className="text-cocoaSoft">Loading…</div>;
  const { booking: b, activities } = data;
  const isActive = b.status === "CONFIRMED" || b.status === "RESCHEDULED";

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="flex items-center justify-between">
        <Link to="/dashboard/bookings" className="text-sm text-cocoaSoft hover:text-primary flex items-center gap-1" data-testid="back-to-bookings">
          <ArrowLeft className="h-4 w-4" /> All bookings
        </Link>
        <StatusPill status={b.status} />
      </div>

      <div>
        <p className="text-xs tracking-[0.18em] uppercase text-cocoaSoft">Booking</p>
        <h1 className="font-heading text-4xl mt-1 leading-tight">{b.service_name}</h1>
        <p className="text-cocoaSoft mt-1">with {b.customer_name}</p>
      </div>

      <div className="grid lg:grid-cols-[1.4fr_1fr] gap-6">
        {/* Left: details */}
        <div className="space-y-6">
          <div className="paper-card p-6 space-y-4">
            <Row icon={CalIcon} label="Date">{b.date}</Row>
            <Row icon={Clock} label="Time">{b.start_time} – {b.end_time} ({b.duration_min} min)</Row>
            <Row icon={IndianRupee} label="Price">₹{b.price}</Row>
            <div className="border-t border-border pt-4 space-y-3">
              <Row icon={Mail} label="Email">{b.customer_email}</Row>
              {b.customer_phone && <Row icon={Phone} label="Phone">{b.customer_phone}</Row>}
              {b.notes && (
                <div className="text-sm">
                  <p className="text-cocoaSoft uppercase tracking-[0.15em] text-xs mb-1">Note from client</p>
                  <p className="italic">"{b.notes}"</p>
                </div>
              )}
            </div>
            {b.cancel_reason && (
              <div className="border-t border-border pt-4 text-sm">
                <p className="text-cocoaSoft uppercase tracking-[0.15em] text-xs mb-1">Cancellation reason</p>
                <p>{b.cancel_reason}</p>
              </div>
            )}
          </div>

          {isActive && (
            <div className="paper-card p-6">
              <h3 className="font-heading text-2xl">Actions</h3>
              <p className="text-cocoaSoft text-sm mt-1">These actions trigger emails to both you and the client.</p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button variant="outline" onClick={() => setResOpen(true)} data-testid="pro-reschedule-button">
                  <RotateCw className="h-4 w-4 mr-2" /> Reschedule
                </Button>
                <Button variant="outline" onClick={() => setCancelOpen(true)} data-testid="pro-cancel-button">
                  <Ban className="h-4 w-4 mr-2" /> Cancel
                </Button>
                <Button variant="ghost" onClick={() => setNsOpen(true)} data-testid="pro-no-show-button">
                  <UserX className="h-4 w-4 mr-2" /> Mark no-show
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* Right: activity */}
        <div className="paper-card p-6" data-testid="activity-timeline">
          <h3 className="font-heading text-2xl flex items-center gap-2"><History className="h-5 w-5" /> Activity</h3>
          <div className="mt-5 space-y-5">
            {activities.length === 0 && <p className="text-sm text-cocoaSoft">No activity yet.</p>}
            {activities.map((a) => (
              <div key={a.id} className="flex gap-3" data-testid={`activity-${a.action_type}`}>
                <div className="mt-1 h-2 w-2 rounded-full bg-primary shrink-0" />
                <div className="text-sm">
                  <p className="font-medium">{ACTION_LABELS[a.action_type] || a.action_type}</p>
                  <p className="text-cocoaSoft text-xs mt-0.5">
                    {new Date(a.created_at).toLocaleString()} · by {a.actor_type}
                  </p>
                  {a.metadata?.reason && (
                    <p className="text-cocoaSoft text-xs mt-1 italic">"{a.metadata.reason}"</p>
                  )}
                  {a.metadata?.to && a.metadata?.from && (
                    <p className="text-cocoaSoft text-xs mt-1">
                      → {a.metadata.to.date} {a.metadata.to.start_time}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <RescheduleDialog open={resOpen} onOpenChange={setResOpen} booking={b} mode="pro" onDone={load} />
      <CancelDialog open={cancelOpen} onOpenChange={setCancelOpen} booking={b} mode="pro" onDone={load} />
      <NoShowDialog open={nsOpen} onOpenChange={setNsOpen} booking={b} onDone={load} />
    </div>
  );
}

function Row({ icon: Icon, label, children }) {
  return (
    <div className="flex items-start gap-3 text-sm">
      <Icon className="h-4 w-4 text-cocoaSoft mt-0.5" />
      <div>
        <p className="text-cocoaSoft uppercase tracking-[0.15em] text-xs">{label}</p>
        <p className="font-medium mt-0.5">{children}</p>
      </div>
    </div>
  );
}

// --- Pro reschedule dialog (uses /me endpoints) ---------------------
export function RescheduleDialog({ open, onOpenChange, booking, mode, token, onDone }) {
  const [date, setDate] = useState(null);
  const [slots, setSlots] = useState([]);
  const [slot, setSlot] = useState(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) { setDate(null); setSlot(null); setSlots([]); setReason(""); }
  }, [open]);

  useEffect(() => {
    if (!date) return;
    const iso = date.toISOString().slice(0, 10);
    const req = mode === "pro"
      ? api.get(`/me/bookings/${booking.id}/reschedule-slots`, { params: { date: iso } })
      : api.get(`/public/bookings/${booking.id}/slots`, { params: { date: iso, token } });
    req.then((r) => setSlots(r.data.slots)).catch(() => setSlots([]));
  }, [date, booking.id, mode, token]);

  const submit = async () => {
    if (!date || !slot) return;
    setBusy(true);
    try {
      const iso = date.toISOString().slice(0, 10);
      const url = mode === "pro"
        ? `/me/bookings/${booking.id}/reschedule`
        : `/public/bookings/${booking.id}/reschedule`;
      const cfg = mode === "pro" ? {} : { params: { token } };
      await api.post(url, { date: iso, start_time: slot, reason }, cfg);
      toast.success("Booking rescheduled");
      onOpenChange(false);
      onDone && onDone();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Could not reschedule");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="font-heading text-2xl">Reschedule booking</DialogTitle>
        </DialogHeader>
        <div className="grid md:grid-cols-2 gap-4 mt-3">
          <div className="paper-card p-2 flex justify-center" data-testid="reschedule-calendar">
            <Calendar mode="single" selected={date} onSelect={setDate} disabled={(d) => d < new Date(new Date().setHours(0,0,0,0))} />
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.15em] text-cocoaSoft mb-3">Available times</p>
            {!date && <p className="text-cocoaSoft text-sm">Pick a date first.</p>}
            {date && slots.length === 0 && <p className="text-cocoaSoft text-sm">No slots on this day.</p>}
            <div className="grid grid-cols-3 gap-2 max-h-64 overflow-y-auto" data-testid="reschedule-slots">
              {slots.map((s) => (
                <button key={s} type="button" onClick={() => setSlot(s)}
                  className={`px-2 py-2 rounded-lg border text-sm transition-all ${slot === s ? "border-primary bg-primary/5" : "border-border bg-white hover:border-primary"}`}
                  data-testid={`reschedule-slot-${s}`}>
                  {s}
                </button>
              ))}
            </div>
            <div className="mt-4">
              <p className="text-xs uppercase tracking-[0.15em] text-cocoaSoft mb-2">Reason (optional)</p>
              <Textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why are you rescheduling?" data-testid="reschedule-reason-input" />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={submit} disabled={!date || !slot || busy} className="rounded-full" data-testid="reschedule-confirm-button">
            {busy ? "Saving…" : "Confirm reschedule"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function CancelDialog({ open, onOpenChange, booking, mode, token, onDone }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      const url = mode === "pro"
        ? `/me/bookings/${booking.id}/cancel`
        : `/public/bookings/${booking.id}/cancel`;
      const cfg = mode === "pro" ? {} : { params: { token } };
      await api.post(url, { reason }, cfg);
      toast.success("Booking cancelled");
      onOpenChange(false);
      onDone && onDone();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Could not cancel");
    } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle className="font-heading text-2xl">Cancel booking</DialogTitle></DialogHeader>
        <div className="flex items-start gap-3 p-3 rounded-lg bg-rose-50 border border-rose-200 text-sm">
          <AlertTriangle className="h-4 w-4 text-rose-600 mt-0.5 shrink-0" />
          <p>Both parties will be emailed. This can't be undone.</p>
        </div>
        <Textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason for cancellation (optional)" data-testid="cancel-reason-input" className="mt-3" />
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Keep booking</Button>
          <Button onClick={submit} disabled={busy} className="rounded-full bg-rose-600 hover:bg-rose-700 text-white" data-testid="cancel-confirm-button">
            {busy ? "Cancelling…" : "Cancel booking"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function NoShowDialog({ open, onOpenChange, booking, onDone }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      await api.post(`/me/bookings/${booking.id}/no-show`, { reason });
      toast.success("Marked as no-show");
      onOpenChange(false);
      onDone && onDone();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Action failed");
    } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle className="font-heading text-2xl">Mark as no-show</DialogTitle></DialogHeader>
        <p className="text-sm text-cocoaSoft">Use this when the client didn't show up. No emails are sent.</p>
        <Textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Notes (optional)" className="mt-3" data-testid="no-show-reason-input" />
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Back</Button>
          <Button onClick={submit} disabled={busy} className="rounded-full" data-testid="no-show-confirm-button">
            {busy ? "Saving…" : "Mark no-show"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
