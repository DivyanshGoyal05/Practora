import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api from "@/lib/api";
import { Check, Calendar, Clock, Video, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export default function BookingConfirmation() {
  const { id } = useParams();
  const [b, setB] = useState(null);

  useEffect(() => {
    api.get(`/bookings/${id}`).then((r) => setB(r.data));
  }, [id]);

  if (!b) return <div className="min-h-screen grid place-items-center"><div className="h-8 w-8 border-2 border-primary border-t-transparent rounded-full animate-spin" /></div>;

  const copyMeet = () => {
    navigator.clipboard.writeText(b.meet_link);
    toast.success("Meeting link copied");
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="glass-nav">
        <div className="max-w-3xl mx-auto px-6 h-16 flex items-center">
          <Link to="/" className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-full bg-primary text-primary-foreground grid place-items-center font-heading">P</div>
            <span className="font-heading text-xl">Practora</span>
          </Link>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-6 py-16 animate-fade-up" data-testid="booking-confirmation">
        <div className="h-14 w-14 rounded-full bg-primary/10 text-primary grid place-items-center mb-6">
          <Check className="h-7 w-7" />
        </div>
        <p className="text-xs tracking-[0.18em] uppercase text-cocoaSoft">Booking confirmed</p>
        <h1 className="font-heading text-5xl mt-2 leading-tight">You're all set, {b.customer_name.split(" ")[0]}.</h1>
        <p className="text-cocoaSoft mt-3">A confirmation has been recorded. Save these details:</p>

        <div className="paper-card p-6 mt-8 space-y-4" data-testid="confirmation-details">
          <div className="flex items-center gap-3">
            <Calendar className="h-5 w-5 text-primary" />
            <div>
              <p className="font-medium">{b.date}</p>
              <p className="text-sm text-cocoaSoft">{b.start_time} – {b.end_time} ({b.duration_min} min)</p>
            </div>
          </div>
          <div className="border-t border-border pt-4">
            <p className="text-xs uppercase tracking-[0.15em] text-cocoaSoft">With</p>
            <p className="font-medium mt-1">{b.professional?.name}</p>
            <p className="text-sm text-cocoaSoft">{b.professional?.category}</p>
          </div>
          <div className="border-t border-border pt-4">
            <p className="text-xs uppercase tracking-[0.15em] text-cocoaSoft">Service</p>
            <p className="font-medium mt-1">{b.service_name}</p>
            <p className="text-sm text-cocoaSoft">₹{b.price}</p>
          </div>

          {b.meet_link && (
            <div className="border-t border-border pt-4">
              <p className="text-xs uppercase tracking-[0.15em] text-cocoaSoft flex items-center gap-1"><Video className="h-3.5 w-3.5" /> Meeting link</p>
              <div className="flex items-center gap-2 mt-2">
                <a href={b.meet_link} target="_blank" rel="noreferrer" className="flex-1 truncate font-mono text-sm text-primary hover:underline" data-testid="meet-link">{b.meet_link}</a>
                <Button size="sm" variant="outline" onClick={copyMeet} data-testid="copy-meet-button">
                  <Copy className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          )}
        </div>

        <div className="mt-10 flex flex-wrap gap-3">
          <Link to={`/${b.professional?.slug}`}>
            <Button variant="outline" className="rounded-full">Book another session</Button>
          </Link>
          <Link to="/">
            <Button variant="ghost" className="rounded-full">Back to Practora</Button>
          </Link>
        </div>
      </main>
    </div>
  );
}
