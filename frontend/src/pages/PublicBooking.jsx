import React, { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import api, { formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Calendar } from "@/components/ui/calendar";
import { Clock, IndianRupee, MapPin, Globe, Instagram, MessageCircle, ArrowLeft, Check, FileText } from "lucide-react";
import { toast } from "sonner";
import IntakeFormRenderer, { validateIntakeAnswers } from "@/components/IntakeFormRenderer";

function NotFound() {
  return (
    <div className="min-h-screen grid place-items-center text-center px-6">
      <div>
        <p className="font-heading text-6xl">404</p>
        <p className="text-cocoaSoft mt-2">This booking page doesn't exist.</p>
        <Link to="/" className="text-primary hover:underline mt-4 inline-block">← Back to Practora</Link>
      </div>
    </div>
  );
}

export default function PublicBooking() {
  const { slug } = useParams();
  const nav = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [step, setStep] = useState("service"); // service | datetime | intake | details | done
  const [selectedService, setSelectedService] = useState(null);
  const [date, setDate] = useState(null);
  const [slots, setSlots] = useState([]);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [time, setTime] = useState(null);
  const [intakeAnswers, setIntakeAnswers] = useState({});
  const [form, setForm] = useState({ customer_name: "", customer_email: "", customer_phone: "", notes: "" });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.get(`/p/${slug}`)
      .then((r) => setData(r.data))
      .catch(() => setError(true));
  }, [slug]);

  useEffect(() => {
    if (!selectedService || !date) return;
    const iso = date.toISOString().slice(0, 10);
    setSlotsLoading(true);
    setTime(null);
    api.get(`/p/${slug}/slots`, { params: { date: iso, service_id: selectedService.id } })
      .then((r) => setSlots(r.data.slots))
      .finally(() => setSlotsLoading(false));
  }, [selectedService, date, slug]);

  if (error) return <NotFound />;
  if (!data) return <div className="min-h-screen grid place-items-center"><div className="h-8 w-8 border-2 border-primary border-t-transparent rounded-full animate-spin" /></div>;

  const { professional: p, services, booking_enabled } = data;
  if (booking_enabled === false) {
    return (
      <div className="min-h-screen grid place-items-center text-center px-6">
        <div className="max-w-md paper-card p-10" data-testid="pro-unavailable">
          {p.photo_url && <img src={p.photo_url} alt={p.name} className="w-20 h-20 rounded-full object-cover mx-auto" />}
          <p className="text-xs tracking-[0.18em] uppercase text-cocoaSoft mt-4">{p.category}</p>
          <h1 className="font-heading text-3xl mt-1">{p.name}</h1>
          <p className="text-cocoaSoft mt-4">This booking page is temporarily unavailable. Please check back soon.</p>
          <Link to="/" className="text-primary hover:underline mt-6 inline-block">← Back to Practora</Link>
        </div>
      </div>
    );
  }
  const intakeQuestions = selectedService?.intake_questions || [];
  const hasIntake = intakeQuestions.length > 0;

  const goBack = () => {
    if (step === "datetime") setStep("service");
    else if (step === "intake") setStep("datetime");
    else if (step === "details") setStep(hasIntake ? "intake" : "datetime");
  };

  const submit = async (e) => {
    e.preventDefault();
    // Final validation of intake (in case user manipulated step)
    if (hasIntake) {
      const errs = validateIntakeAnswers(intakeQuestions, intakeAnswers);
      if (errs.length) { toast.error(`${errs[0].field}: ${errs[0].message}`); return; }
    }
    setSubmitting(true);
    try {
      const payload = {
        service_id: selectedService.id,
        date: date.toISOString().slice(0, 10),
        start_time: time,
        ...form,
        intake_answers: Object.entries(intakeAnswers)
          .filter(([_, v]) => (v ?? "").toString().trim() !== "")
          .map(([question_id, answer]) => ({ question_id, answer: String(answer) })),
      };
      const { data: booking } = await api.post(`/p/${slug}/book`, payload);
      nav(`/booking/${booking.id}`);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Booking failed");
    } finally {
      setSubmitting(false);
    }
  };

  const handleSlotPick = (s) => {
    setTime(s);
    setStep(hasIntake ? "intake" : "details");
  };

  const continueFromIntake = () => {
    const errs = validateIntakeAnswers(intakeQuestions, intakeAnswers);
    if (errs.length) { toast.error(`${errs[0].field}: ${errs[0].message}`); return; }
    setStep("details");
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="glass-nav">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-full bg-primary text-primary-foreground grid place-items-center font-heading">P</div>
            <span className="font-heading text-xl">Practora</span>
          </Link>
          <span className="text-xs text-cocoaSoft">Secure booking</span>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10 grid lg:grid-cols-[1fr_1.3fr] gap-10">
        {/* Left: Professional bio (sticky) */}
        <aside className="lg:sticky lg:top-24 lg:self-start" data-testid="pro-bio">
          <div className="paper-card p-6">
            {p.photo_url && (
              <img src={p.photo_url} alt={p.name} className="w-24 h-24 rounded-full object-cover" />
            )}
            <p className="text-xs tracking-[0.18em] uppercase text-cocoaSoft mt-4">{p.category}</p>
            <h1 className="font-heading text-4xl mt-1 leading-tight" data-testid="pro-name">{p.name}</h1>
            {p.experience && <p className="text-sm text-cocoaSoft mt-1">{p.experience} of experience</p>}
            {p.bio && <p className="text-sm text-foreground/80 mt-4 leading-relaxed">{p.bio}</p>}

            {(p.languages || []).length > 0 && (
              <div className="mt-5">
                <p className="text-xs tracking-[0.15em] uppercase text-cocoaSoft mb-2">Speaks</p>
                <div className="flex flex-wrap gap-1.5">
                  {p.languages.map((l) => (
                    <span key={l} className="text-xs px-2 py-0.5 rounded-full bg-secondary">{l}</span>
                  ))}
                </div>
              </div>
            )}

            <div className="mt-5 flex flex-wrap gap-3 text-sm text-cocoaSoft">
              {p.instagram && <a href={p.instagram} target="_blank" rel="noreferrer" className="hover:text-primary flex items-center gap-1"><Instagram className="h-4 w-4" /> Instagram</a>}
              {p.website && <a href={p.website} target="_blank" rel="noreferrer" className="hover:text-primary flex items-center gap-1"><Globe className="h-4 w-4" /> Website</a>}
              {p.whatsapp && <span className="flex items-center gap-1"><MessageCircle className="h-4 w-4" /> {p.whatsapp}</span>}
            </div>
          </div>
        </aside>

        {/* Right: Booking flow */}
        <main>
          {/* Step header */}
          <div className="flex items-center gap-3 text-sm text-cocoaSoft mb-6">
            {step !== "service" && (
              <button onClick={goBack} className="flex items-center gap-1 hover:text-primary" data-testid="back-button">
                <ArrowLeft className="h-4 w-4" /> Back
              </button>
            )}
            <div className="flex items-center gap-2">
              <Step active={step === "service"} done={["datetime","intake","details"].includes(step)} n="1" label="Service" />
              <div className="w-6 h-px bg-border" />
              <Step active={step === "datetime"} done={["intake","details"].includes(step)} n="2" label="Date & time" />
              {hasIntake && <>
                <div className="w-6 h-px bg-border" />
                <Step active={step === "intake"} done={step === "details"} n="3" label="Intake" />
              </>}
              <div className="w-6 h-px bg-border" />
              <Step active={step === "details"} n={hasIntake ? "4" : "3"} label="Your details" />
            </div>
          </div>

          {/* Step 1 — service */}
          {step === "service" && (
            <div className="space-y-3 animate-fade-up" data-testid="services-step">
              <h2 className="font-heading text-3xl mb-2">Choose a service</h2>
              {services.length === 0 && (
                <p className="paper-card p-6 text-cocoaSoft">No services available yet.</p>
              )}
              {services.map((s) => (
                <button
                  key={s.id}
                  onClick={() => { setSelectedService(s); setStep("datetime"); }}
                  className="w-full text-left paper-card p-5 hover:border-primary transition-all hover:-translate-y-0.5"
                  data-testid={`service-option-${s.id}`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <p className="font-heading text-2xl leading-tight">{s.name}</p>
                      {s.description && <p className="text-sm text-cocoaSoft mt-2 leading-relaxed">{s.description}</p>}
                      <div className="flex items-center gap-4 mt-3 text-sm text-cocoaSoft">
                        <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> {s.duration_min} min</span>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-heading text-2xl">₹{s.price}</p>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}

          {/* Step 2 — date & time */}
          {step === "datetime" && selectedService && (
            <div className="animate-fade-up space-y-6" data-testid="datetime-step">
              <div className="paper-card p-4 flex items-center justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.15em] text-cocoaSoft">Selected</p>
                  <p className="font-medium">{selectedService.name} · {selectedService.duration_min} min · ₹{selectedService.price}</p>
                </div>
              </div>

              <div className="grid md:grid-cols-2 gap-6">
                <div className="paper-card p-2 flex justify-center" data-testid="calendar-wrapper">
                  <Calendar
                    mode="single"
                    selected={date}
                    onSelect={setDate}
                    disabled={(d) => d < new Date(new Date().setHours(0,0,0,0))}
                  />
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.15em] text-cocoaSoft mb-3">Available times</p>
                  {!date && <p className="text-cocoaSoft text-sm">Pick a date to see slots.</p>}
                  {date && slotsLoading && <p className="text-cocoaSoft text-sm">Loading slots…</p>}
                  {date && !slotsLoading && slots.length === 0 && (
                    <p className="paper-card p-4 text-sm text-cocoaSoft" data-testid="no-slots-message">No slots available on this day.</p>
                  )}
                  <div className="grid grid-cols-3 gap-2" data-testid="slots-grid">
                    {slots.map((s) => (
                      <button
                        key={s}
                        onClick={() => handleSlotPick(s)}
                        className={`px-3 py-2.5 rounded-lg border text-sm transition-all hover:border-primary hover:-translate-y-0.5 ${time === s ? "border-primary bg-primary/5" : "border-border bg-white"}`}
                        data-testid={`slot-${s}`}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Step 2.5 — intake (only if service has questions) */}
          {step === "intake" && selectedService && hasIntake && (
            <div className="animate-fade-up space-y-6" data-testid="intake-step">
              <div className="paper-card p-4 flex items-center justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.15em] text-cocoaSoft">Selected</p>
                  <p className="font-medium">{selectedService.name} · {date?.toDateString()} at {time}</p>
                </div>
              </div>
              <div>
                <h2 className="font-heading text-3xl flex items-center gap-2"><FileText className="h-6 w-6 text-primary" /> A few quick questions</h2>
                <p className="text-cocoaSoft text-sm mt-1">{p.name} would like to know a bit before your session.</p>
              </div>
              <div className="paper-card p-5">
                <IntakeFormRenderer
                  questions={intakeQuestions}
                  answers={intakeAnswers}
                  onChange={(qid, v) => setIntakeAnswers((p) => ({ ...p, [qid]: v }))}
                  testidPrefix="intake"
                />
              </div>
              <Button size="lg" onClick={continueFromIntake} className="rounded-full btn-lift" data-testid="intake-continue-button">
                Continue
              </Button>
            </div>
          )}

          {/* Step 3 — details */}
          {step === "details" && selectedService && date && time && (
            <form onSubmit={submit} className="animate-fade-up space-y-5" data-testid="details-step">
              <div className="paper-card p-4">
                <p className="text-xs uppercase tracking-[0.15em] text-cocoaSoft">You're booking</p>
                <p className="font-medium mt-1">{selectedService.name}</p>
                <p className="text-sm text-cocoaSoft">{date.toDateString()} at {time} · ₹{selectedService.price}</p>
              </div>

              <div className="space-y-2">
                <Label>Your name</Label>
                <Input value={form.customer_name} onChange={(e) => setForm({ ...form, customer_name: e.target.value })} required data-testid="customer-name-input" />
              </div>
              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Email</Label>
                  <Input type="email" value={form.customer_email} onChange={(e) => setForm({ ...form, customer_email: e.target.value })} required data-testid="customer-email-input" />
                </div>
                <div className="space-y-2">
                  <Label>Phone (optional)</Label>
                  <Input value={form.customer_phone} onChange={(e) => setForm({ ...form, customer_phone: e.target.value })} data-testid="customer-phone-input" />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Anything to share (optional)</Label>
                <Textarea rows={3} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="What would you like to focus on?" data-testid="customer-notes-input" />
              </div>

              <Button type="submit" size="lg" disabled={submitting} className="rounded-full btn-lift w-full md:w-auto" data-testid="confirm-booking-button">
                {submitting ? "Booking…" : `Confirm booking — ₹${selectedService.price}`}
              </Button>
              <p className="text-xs text-cocoaSoft">Payment collection coming soon. Your slot will be reserved.</p>
            </form>
          )}
        </main>
      </div>
    </div>
  );
}

function Step({ active, done, n, label }) {
  return (
    <div className={`flex items-center gap-1.5 ${active ? "text-foreground font-medium" : done ? "text-primary" : "text-cocoaSoft"}`}>
      <span className={`h-5 w-5 rounded-full grid place-items-center text-xs ${active ? "bg-primary text-primary-foreground" : done ? "bg-primary/20 text-primary" : "bg-secondary"}`}>
        {done ? <Check className="h-3 w-3" /> : n}
      </span>
      <span className="hidden sm:inline">{label}</span>
    </div>
  );
}
