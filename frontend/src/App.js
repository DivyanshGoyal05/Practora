import "@/index.css";
import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { Toaster } from "@/components/ui/sonner";

import Marketing from "@/pages/Marketing";
import Login from "@/pages/Login";
import Signup from "@/pages/Signup";
import Dashboard from "@/pages/Dashboard";
import Services from "@/pages/Services";
import Availability from "@/pages/Availability";
import Profile from "@/pages/Profile";
import Policies from "@/pages/Policies";
import BookingsList from "@/pages/BookingsList";
import BookingDetail from "@/pages/BookingDetail";
import PublicBooking from "@/pages/PublicBooking";
import BookingConfirmation from "@/pages/BookingConfirmation";
import ManageBooking from "@/pages/ManageBooking";
import DashboardLayout from "@/components/DashboardLayout";

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading || user === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="h-8 w-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Marketing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />

      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="services" element={<Services />} />
        <Route path="availability" element={<Availability />} />
        <Route path="profile" element={<Profile />} />
        <Route path="policies" element={<Policies />} />
        <Route path="bookings" element={<BookingsList />} />
        <Route path="bookings/:id" element={<BookingDetail />} />
      </Route>

      <Route path="/booking/:id/manage" element={<ManageBooking />} />
      <Route path="/booking/:id" element={<BookingConfirmation />} />
      {/* Public booking page LAST so it doesn't shadow other routes */}
      <Route path="/:slug" element={<PublicBooking />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
        <Toaster position="top-right" richColors />
      </BrowserRouter>
    </AuthProvider>
  );
}
