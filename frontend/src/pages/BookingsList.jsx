import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import { ArrowRight } from "lucide-react";

const STATUS_STYLES = {
  CONFIRMED: "bg-green-50 text-green-700 border-green-200",
  RESCHEDULED: "bg-amber-50 text-amber-800 border-amber-200",
  CANCELLED: "bg-rose-50 text-rose-700 border-rose-200",
  COMPLETED: "bg-stone-100 text-stone-700 border-stone-200",
  NO_SHOW: "bg-stone-100 text-stone-700 border-stone-200",
};

export default function BookingsList() {
  const [bookings, setBookings] = useState([]);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/me/bookings").then((r) => { setBookings(r.data); setLoading(false); });
  }, []);

  if (loading) return <div className="text-cocoaSoft">Loading…</div>;

  const today = new Date().toISOString().slice(0, 10);
  const filters = [
    { key: "all", label: "All" },
    { key: "upcoming", label: "Upcoming" },
    { key: "past", label: "Past" },
    { key: "cancelled", label: "Cancelled" },
  ];

  const filtered = bookings.filter((b) => {
    if (filter === "upcoming") return ["CONFIRMED", "RESCHEDULED"].includes(b.status) && b.date >= today;
    if (filter === "past") return ["COMPLETED", "NO_SHOW"].includes(b.status);
    if (filter === "cancelled") return b.status === "CANCELLED";
    return true;
  });

  return (
    <div className="space-y-6 animate-fade-up">
      <div>
        <h1 className="font-heading text-4xl">Bookings</h1>
        <p className="text-cocoaSoft mt-1">All upcoming and past sessions.</p>
      </div>

      <div className="flex flex-wrap gap-2" data-testid="booking-filters">
        {filters.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-3 py-1.5 rounded-full text-sm transition-colors ${filter === f.key ? "bg-primary text-primary-foreground" : "bg-secondary text-foreground hover:bg-secondary/70"}`}
            data-testid={`filter-${f.key}`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="paper-card p-12 text-center" data-testid="bookings-empty">
          <p className="font-heading text-3xl">No bookings here</p>
          <p className="text-cocoaSoft mt-2">Share your booking link to get your first client.</p>
        </div>
      ) : (
        <div className="paper-card divide-y divide-border" data-testid="bookings-list">
          {filtered.map((b) => (
            <Link to={`/dashboard/bookings/${b.id}`} key={b.id} className="block p-4 md:p-5 hover:bg-secondary/40 transition-colors" data-testid={`booking-${b.id}`}>
              <div className="grid md:grid-cols-[140px_1fr_auto_auto] gap-3 md:items-center">
                <div>
                  <p className="font-medium">{b.date}</p>
                  <p className="text-sm text-cocoaSoft">{b.start_time} – {b.end_time}</p>
                </div>
                <div className="min-w-0">
                  <p className="font-medium">{b.customer_name}</p>
                  <p className="text-sm text-cocoaSoft truncate">{b.customer_email} · {b.service_name} · {b.duration_min} min</p>
                </div>
                <span className={`text-xs uppercase tracking-[0.15em] px-2.5 py-1 rounded-full border w-fit ${STATUS_STYLES[b.status] || ""}`}>
                  {b.status?.replace("_", " ")}
                </span>
                <div className="flex items-center gap-3">
                  <p className="font-medium">₹{b.price}</p>
                  <ArrowRight className="h-4 w-4 text-cocoaSoft" />
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
