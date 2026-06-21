import React from "react";
import { Outlet, NavLink, useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { LayoutGrid, Calendar, Briefcase, Clock, UserCircle, LogOut, ExternalLink, Shield } from "lucide-react";

const items = [
  { to: "/dashboard", label: "Overview", icon: LayoutGrid, end: true, testid: "nav-overview" },
  { to: "/dashboard/bookings", label: "Bookings", icon: Calendar, testid: "nav-bookings" },
  { to: "/dashboard/services", label: "Services", icon: Briefcase, testid: "nav-services" },
  { to: "/dashboard/availability", label: "Availability", icon: Clock, testid: "nav-availability" },
  { to: "/dashboard/policies", label: "Policies", icon: Shield, testid: "nav-policies" },
  { to: "/dashboard/profile", label: "Profile", icon: UserCircle, testid: "nav-profile" },
];

export default function DashboardLayout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();

  const handleLogout = async () => {
    await logout();
    nav("/login");
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="glass-nav sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <Link to="/dashboard" className="flex items-center gap-2" data-testid="logo-link">
            <div className="h-8 w-8 rounded-full bg-primary text-primary-foreground grid place-items-center font-heading text-lg">P</div>
            <span className="font-heading text-xl tracking-tight">Practora</span>
          </Link>
          <div className="flex items-center gap-3">
            {user?.slug && (
              <a
                href={`/${user.slug}`}
                target="_blank"
                rel="noreferrer"
                className="hidden md:inline-flex items-center gap-2 text-sm text-cocoaSoft hover:text-primary transition-colors"
                data-testid="view-public-page-link"
              >
                <ExternalLink className="h-4 w-4" /> practora.in/{user.slug}
              </a>
            )}
            <Button variant="ghost" size="sm" onClick={handleLogout} data-testid="logout-button">
              <LogOut className="h-4 w-4 mr-2" /> Sign out
            </Button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-8">
        <aside className="lg:sticky lg:top-24 lg:self-start">
          <nav className="flex lg:flex-col gap-1 overflow-x-auto" data-testid="dashboard-sidebar">
            {items.map((it) => (
              <NavLink
                key={it.to}
                to={it.to}
                end={it.end}
                data-testid={it.testid}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-lg text-sm whitespace-nowrap transition-colors ${
                    isActive ? "bg-primary/10 text-primary font-medium" : "text-cocoaSoft hover:bg-secondary hover:text-foreground"
                  }`
                }
              >
                <it.icon className="h-4 w-4" /> {it.label}
              </NavLink>
            ))}
          </nav>
        </aside>

        <main className="min-w-0">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
