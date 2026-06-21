import React, { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";

const CATEGORIES = ["Astrologer", "Doctor", "Therapist", "Dietician", "Coach", "Yoga Teacher", "Tutor", "Consultant"];

export default function Profile() {
  const { user, refresh } = useAuth();
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (user) {
      setForm({
        name: user.name || "",
        bio: user.bio || "",
        category: user.category || CATEGORIES[0],
        photo_url: user.photo_url || "",
        experience: user.experience || "",
        languages: (user.languages || []).join(", "),
        whatsapp: user.whatsapp || "",
        instagram: user.instagram || "",
        website: user.website || "",
        meet_link: user.meet_link || "",
      });
    }
  }, [user]);

  if (!form) return null;

  const set = (k) => (e) => setForm((p) => ({ ...p, [k]: e.target?.value ?? e }));

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {
        ...form,
        languages: form.languages.split(",").map((s) => s.trim()).filter(Boolean),
      };
      await api.put("/me/profile", payload);
      await refresh();
      toast.success("Profile updated");
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={save} className="space-y-8 animate-fade-up max-w-3xl" data-testid="profile-form">
      <div>
        <h1 className="font-heading text-4xl">Profile</h1>
        <p className="text-cocoaSoft mt-1">This is what clients see on your booking page.</p>
      </div>

      <div className="paper-card p-6 space-y-5">
        <div className="grid md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Display name</Label>
            <Input value={form.name} onChange={set("name")} data-testid="profile-name-input" />
          </div>
          <div className="space-y-2">
            <Label>Category</Label>
            <Select value={form.category} onValueChange={(v) => setForm((p) => ({ ...p, category: v }))}>
              <SelectTrigger data-testid="profile-category-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                {CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="space-y-2">
          <Label>Bio</Label>
          <Textarea rows={4} value={form.bio} onChange={set("bio")} placeholder="A short, warm introduction to your practice." data-testid="profile-bio-input" />
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Profile photo URL</Label>
            <Input value={form.photo_url} onChange={set("photo_url")} placeholder="https://…" data-testid="profile-photo-input" />
          </div>
          <div className="space-y-2">
            <Label>Experience</Label>
            <Input value={form.experience} onChange={set("experience")} placeholder="e.g. 8 years" data-testid="profile-experience-input" />
          </div>
          <div className="space-y-2 md:col-span-2">
            <Label>Languages (comma separated)</Label>
            <Input value={form.languages} onChange={set("languages")} placeholder="English, Hindi" data-testid="profile-languages-input" />
          </div>
        </div>
      </div>

      <div className="paper-card p-6 space-y-5">
        <h3 className="font-heading text-2xl">Contact & Links</h3>
        <div className="grid md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>WhatsApp number</Label>
            <Input value={form.whatsapp} onChange={set("whatsapp")} placeholder="+91 98765 43210" data-testid="profile-whatsapp-input" />
          </div>
          <div className="space-y-2">
            <Label>Instagram URL</Label>
            <Input value={form.instagram} onChange={set("instagram")} placeholder="https://instagram.com/…" data-testid="profile-instagram-input" />
          </div>
          <div className="space-y-2">
            <Label>Website URL</Label>
            <Input value={form.website} onChange={set("website")} placeholder="https://…" data-testid="profile-website-input" />
          </div>
          <div className="space-y-2">
            <Label>Google Meet link</Label>
            <Input value={form.meet_link} onChange={set("meet_link")} placeholder="https://meet.google.com/…" data-testid="profile-meet-input" />
            <p className="text-xs text-cocoaSoft">Shared automatically with clients after they book.</p>
          </div>
        </div>
      </div>

      <div className="flex justify-end">
        <Button type="submit" disabled={saving} className="rounded-full btn-lift" data-testid="save-profile-button">
          {saving ? "Saving…" : "Save profile"}
        </Button>
      </div>
    </form>
  );
}
