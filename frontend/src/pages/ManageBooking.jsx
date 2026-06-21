import React, { useEffect, useState } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import api, { formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Calendar } from "@/components/ui/calendar";
import { toast } from "sonner";
import { Calendar as CalIcon, Clock, ArrowLeft, AlertTriangle, RotateCw, Ban, Check } from "lucide-react";

const STATUS_STYLES = {
  CONFIRMED: "bg-green-50 text-green-700 border-green-200",
  RESCHEDULED: "bg-amber-50 text-amber-800 border-amber-200",
  CANCELLED: "bg-rose-50 text-rose-700 border-rose-200",
  COMPLETED: "bg-stone-100 text-stone-700 border-stone-200",
  NO_SHOW: "bg-stone-100 text-stone-700 border-stone-200",
};

export default function ManageBooking() {
  const { id } = useParams();
  const [sp] = useSearchParams();
  const token = sp.get("token") || "";

  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [view, setView] = useState("home"); // home | reschedule | cancel | done

  const load = async () => {
    try {
      const { data } = await api.get(`/public/bookings/${id}`, { params: { token } });
      setData(data);
    } catch (err) {
      setError(err.response?.data?.detail || "Could not load booking");
    }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id, token]);

  if (error) {
    return (
      <div className="min-h-screen grid place-items-center text-center px-6">
        <div className="paper-card p-10 max-w-md">
          <p className="font-heading text-3xl">Link expired or invalid</p>
          <p className="text-cocoaSoft mt-3 text-sm">{error}</p>
          <Link to="/" className="text-primary hover:underline text-sm mt-6 inline-block">← Back to Practora</Link>
        </div>
      </div>
    );
  }
  if (!data) return <div className="min-h-screen grid place-items-center"><div className="h-8 w-8 border-2 border-primary border-t-transparent rounded-full animate-spin" /></div>;

  const { booking: b, professional: p, policies, permissions } = data;

  return (
    <div className="min-h-screen bg-background">
      <header className="glass-nav">
        <div className="max-w-3xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-full bg-primary text-primary-foreground grid place-items-center font-heading">P</div>
            <span className="font-heading text-xl">Practora</span>
          </Link>
          <span className="text-xs text-cocoaSoft">Manage your booking</span>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-6 py-12 animate-fade-up">
        {view !== "home" && (
          <button onClick={() => setView("home")} className="text-sm text-cocoaSoft hover:text-primary flex items-center gap-1 mb-4" data-testid="back-button">
            <ArrowLeft className="h-4 w-4" /> Back
          </button>
        )}

        {view === "home" && (
          <>
            <div className="flex items-center justify-between">
              <p className="text-xs tracking-[0.18em] uppercase text-cocoaSoft">Your booking</p>
              <span className={`text-xs uppercase tracking-[0.15em] px-2.5 py-1 rounded-full border ${STATUS_STYLES[b.status]}`} data-testid="booking-status">
                {b.status.replace("_", " ")}
              </span>
            </div>
            <h1 className="font-heading text-4xl mt-1 leading-tight">{b.service_name}</h1>
            <p className="text-cocoaSoft mt-1">with {p.name}</p>

            <div className="paper-card p-6 mt-6 space-y-4" data-testid="booking-summary">
              <div className="flex items-center gap-3">
                <CalIcon className="h-5 w-5 text-primary" />
                <div>
                  <p className="font-medium">{b.date}</p>
                  <p className="text-sm text-cocoaSoft">{b.start_time} – {b.end_time}</p>
                </div>
              </div>
              {b.meet_link && b.status !== "CANCELLED" && (
                <div className="border-t border-border pt-4 text-sm">
                  <p className="text-xs uppercase tracking-[0.15em] text-cocoaSoft">Meeting link</p>
                  <a href={b.meet_link} target="_blank" rel="noreferrer" className="text-primary hover:underline break-all" data-testid="meet-link">{b.meet_link}</a>
                </div>
              )}
              {b.cancel_reason && (
                <div className="border-t border-border pt-4 text-sm">
                  <p className="text-xs uppercase tracking-[0.15em] text-cocoaSoft">Cancellation reason</p>
                  <p className="mt-1">{b.cancel_reason}</p>
                </div>
              )}
            </div>

            {permissions.reason_blocked && (
              <div className="mt-6 paper-card p-4 flex items-start gap-3 bg-amber-50/40 border-amber-200" data-testid="blocked-notice">
                <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
                <p className="text-sm">{permissions.reason_blocked}</p>
              </div>
            )}

            <div className="mt-6 flex flex-wrap gap-3">
              <Button variant="outline" disabled={!permissions.can_reschedule} onClick={() => setView("reschedule")} className="rounded-full" data-testid="open-reschedule-button">
                <RotateCw className="h-4 w-4 mr-2" /> Reschedule
              </Button>
              <Button variant="outline" disabled={!permissions.can_cancel} onClick={() => setView("cancel")} className="rounded-full" data-testid="open-cancel-button">
                <Ban className="h-4 w-4 mr-2" /> Cancel
              </Button>
            </div>

            <p className="text-xs text-cocoaSoft mt-6">
              Policy: reschedule up to {policies.reschedule_window_hours}h before · cancel up to {policies.cancel_window_hours}h before · max {policies.reschedule_limit} reschedules.
            </p>
          </>
        )}

        {view === "reschedule" && <CustomerReschedule booking={b} token={token} onDone={() => { setView("done"); load(); }} />}
        {view === "cancel" && <CustomerCancel booking={b} token={token} onDone={() => { setView("done"); load(); }} />}
        {view === "done" && (
          <div className="text-center py-10" data-testid="action-done">
            <div className="h-14 w-14 rounded-full bg-primary/10 text-primary grid place-items-center mx-auto"><Check className="h-7 w-7" /></div>
            <p className="font-heading text-3xl mt-4">All done</p>
            <p className="text-cocoaSoft mt-2 text-sm">A confirmation email has been sent.</p>
            <Button onClick={() => setView("home")} className="rounded-full mt-6">View booking</Button>
          </div>
        )}
      </main>
    </div>
  );
}

function CustomerReschedule({ booking, token, onDone }) {
  const [date, setDate] = useState(null);
  const [slots, setSlots] = useState([]);
  const [slot, setSlot] = useState(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!date) return;
    const iso = date.toISOString().slice(0, 10);
    api.get(`/public/bookings/${booking.id}/slots`, { params: { token, date: iso } }).then((r) => setSlots(r.data.slots));
  }, [date, booking.id, token]);

  const submit = async () => {
    if (!date || !slot) return;
    setBusy(true);
    try {
      await api.post(`/public/bookings/${booking.id}/reschedule`,
        { date: date.toISOString().slice(0, 10), start_time: slot, reason }, { params: { token } });
      toast.success("Rescheduled");
      onDone();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Could not reschedule");
    } finally { setBusy(false); }
  };

  return (
    <div data-testid="customer-reschedule-view">
      <h2 className="font-heading text-3xl">Pick a new time</h2>
      <p className="text-cocoaSoft text-sm mt-1">{booking.service_name} · {booking.duration_min} min</p>

      <div className="grid md:grid-cols-2 gap-4 mt-6">
        <div className="paper-card p-2 flex justify-center" data-testid="customer-reschedule-calendar">
          <Calendar mode="single" selected={date} onSelect={setDate} disabled={(d) => d < new Date(new Date().setHours(0,0,0,0))} />
        </div>
        <div>
          <p className="text-xs uppercase tracking-[0.15em] text-cocoaSoft mb-3">Available times</p>
          {!date && <p className="text-sm text-cocoaSoft">Pick a date first.</p>}
          {date && slots.length === 0 && <p className="text-sm text-cocoaSoft">No slots that day.</p>}
          <div className="grid grid-cols-3 gap-2 max-h-64 overflow-y-auto" data-testid="customer-reschedule-slots">
            {slots.map((s) => (
              <button key={s} onClick={() => setSlot(s)} type="button"
                className={`px-2 py-2 rounded-lg border text-sm transition-all ${slot === s ? "border-primary bg-primary/5" : "border-border bg-white hover:border-primary"}`}
                data-testid={`customer-slot-${s}`}>
                {s}
              </button>
            ))}
          </div>
          <div className="mt-4">
            <p className="text-xs uppercase tracking-[0.15em] text-cocoaSoft mb-2">Reason (optional)</p>
            <Textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} data-testid="customer-reschedule-reason" />
          </div>
        </div>
      </div>
      <Button onClick={submit} disabled={!date || !slot || busy} className="rounded-full mt-6 btn-lift" data-testid="customer-reschedule-confirm">
        {busy ? "Rescheduling…" : "Confirm new time"}
      </Button>
    </div>
  );
}

function CustomerCancel({ booking, token, onDone }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      await api.post(`/public/bookings/${booking.id}/cancel`, { reason }, { params: { token } });
      toast.success("Booking cancelled");
      onDone();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Could not cancel");
    } finally { setBusy(false); }
  };

  return (
    <div data-testid="customer-cancel-view">
      <h2 className="font-heading text-3xl">Cancel this booking?</h2>
      <p className="text-cocoaSoft text-sm mt-2">This can't be undone. We'll let the professional know.</p>
      <Textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason (optional)" className="mt-5" data-testid="customer-cancel-reason" />
      <div className="mt-6 flex gap-3">
        <Button onClick={submit} disabled={busy} className="rounded-full bg-rose-600 hover:bg-rose-700 text-white" data-testid="customer-cancel-confirm">
          {busy ? "Cancelling…" : "Yes, cancel booking"}
        </Button>
      </div>
    </div>
  );
}
