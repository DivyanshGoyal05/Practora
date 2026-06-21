import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Calendar, IndianRupee, Users, TrendingUp, ArrowRight, Sparkles, ExternalLink, Copy } from "lucide-react";
import { toast } from "sonner";

function StatBlock({ icon: Icon, label, value, testid }) {
  return (
    <div className="paper-card p-6" data-testid={testid}>
      <div className="flex items-center justify-between">
        <p className="text-xs tracking-[0.15em] uppercase text-cocoaSoft">{label}</p>
        <Icon className="h-4 w-4 text-cocoaSoft" />
      </div>
      <p className="font-heading text-4xl mt-3">{value}</p>
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [bookings, setBookings] = useState([]);

  useEffect(() => {
    api.get("/me/stats").then((r) => setStats(r.data));
    api.get("/me/bookings").then((r) => setBookings(r.data));
  }, []);

  const upcoming = bookings.filter((b) => b.status !== "cancelled").slice(0, 5);
  const pageUrl = user?.slug ? `${window.location.origin}/${user.slug}` : "";

  const copyLink = () => {
    if (!pageUrl) return;
    navigator.clipboard.writeText(pageUrl);
    toast.success("Booking link copied");
  };

  return (
    <div className="space-y-8 animate-fade-up" data-testid="dashboard-overview">
      {/* Greeting + Page card */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2">
          <p className="text-xs tracking-[0.18em] uppercase text-cocoaSoft">Welcome back</p>
          <h1 className="font-heading text-4xl md:text-5xl mt-2 leading-tight">{user?.name}</h1>
          <p className="text-cocoaSoft mt-3 max-w-xl">Your booking page is live. Share your link to start taking bookings.</p>
        </div>
        <div className="paper-card p-5">
          <p className="text-xs tracking-[0.15em] uppercase text-cocoaSoft">Your booking page</p>
          <p className="font-mono text-sm mt-2 break-all" data-testid="public-page-url">{pageUrl}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={copyLink} data-testid="copy-link-button">
              <Copy className="h-3.5 w-3.5 mr-1.5" /> Copy
            </Button>
            <a href={`/${user?.slug}`} target="_blank" rel="noreferrer">
              <Button size="sm" data-testid="open-public-page-button">
                <ExternalLink className="h-3.5 w-3.5 mr-1.5" /> Open
              </Button>
            </a>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatBlock icon={IndianRupee} label="Revenue" value={`₹${stats?.total_revenue ?? 0}`} testid="stat-revenue" />
        <StatBlock icon={Calendar} label="Upcoming" value={stats?.upcoming_sessions ?? 0} testid="stat-upcoming" />
        <StatBlock icon={TrendingUp} label="Total bookings" value={stats?.total_bookings ?? 0} testid="stat-total" />
        <StatBlock icon={Users} label="Repeat clients" value={stats?.repeat_customers ?? 0} testid="stat-repeat" />
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { to: "/dashboard/services", label: "Add a service", desc: "Define what you offer & price." },
          { to: "/dashboard/availability", label: "Set availability", desc: "Choose hours & block dates." },
          { to: "/dashboard/profile", label: "Polish your profile", desc: "Photo, bio, links." },
        ].map((c) => (
          <Link key={c.to} to={c.to} className="paper-card p-5 group hover:border-primary transition-colors" data-testid={`quick-action-${c.to.split("/").pop()}`}>
            <div className="flex items-start justify-between">
              <Sparkles className="h-4 w-4 text-primary" />
              <ArrowRight className="h-4 w-4 text-cocoaSoft group-hover:text-primary group-hover:translate-x-0.5 transition-transform" />
            </div>
            <p className="font-heading text-2xl mt-4 leading-tight">{c.label}</p>
            <p className="text-sm text-cocoaSoft mt-1">{c.desc}</p>
          </Link>
        ))}
      </div>

      {/* Upcoming bookings */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-heading text-2xl">Upcoming bookings</h2>
          <Link to="/dashboard/bookings" className="text-sm text-primary hover:underline" data-testid="view-all-bookings-link">View all →</Link>
        </div>
        {upcoming.length === 0 ? (
          <div className="paper-card p-10 text-center" data-testid="no-bookings-empty">
            <p className="font-heading text-2xl">No bookings yet</p>
            <p className="text-cocoaSoft text-sm mt-2">Once clients book, you'll see them here.</p>
          </div>
        ) : (
          <div className="paper-card divide-y divide-border" data-testid="upcoming-bookings-list">
            {upcoming.map((b) => (
              <div key={b.id} className="p-4 md:p-5 flex flex-col md:flex-row md:items-center gap-3 md:gap-6" data-testid={`booking-row-${b.id}`}>
                <div className="md:w-24 text-sm">
                  <p className="font-medium">{b.date}</p>
                  <p className="text-cocoaSoft">{b.start_time}</p>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{b.customer_name}</p>
                  <p className="text-sm text-cocoaSoft truncate">{b.service_name} · {b.duration_min} min</p>
                </div>
                <div className="text-right">
                  <p className="font-medium">₹{b.price}</p>
                  <p className="text-xs uppercase tracking-[0.15em] text-cocoaSoft">{b.status}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
