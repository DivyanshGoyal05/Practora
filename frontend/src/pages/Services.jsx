import React, { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Plus, Pencil, Trash2, Clock, IndianRupee, FileText, Video, MapPin, Phone } from "lucide-react";
import { toast } from "sonner";
import IntakeFormBuilder from "@/components/IntakeFormBuilder";

const emptyForm = { name: "", description: "", duration_min: 60, price: 1000, cover_image: "", meeting_mode: "video", meeting_details: "" };

const MODE_META = {
  video:     { label: "Video call",   icon: Video,  placeholder: "https://meet.google.com/… (leave empty to set per booking)", help: "Customer will get this link in their confirmation email." },
  in_person: { label: "In person",    icon: MapPin, placeholder: "Clinic address or landmark…",  help: "Customer will see this address in their confirmation." },
  phone:     { label: "Phone call",   icon: Phone,  placeholder: "Phone number you'll call from (optional)", help: "You'll call the customer on the phone number they provided." },
};

export default function Services() {
  const [services, setServices] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);

  const [intakeOpen, setIntakeOpen] = useState(false);
  const [intakeService, setIntakeService] = useState(null);

  const load = async () => {
    const { data } = await api.get("/me/services");
    setServices(data);
  };
  useEffect(() => { load(); }, []);

  const openCreate = () => { setEditing(null); setForm(emptyForm); setOpen(true); };
  const openEdit = (s) => { setEditing(s); setForm({ name: s.name, description: s.description, duration_min: s.duration_min, price: s.price, cover_image: s.cover_image || "", meeting_mode: s.meeting_mode || "video", meeting_details: s.meeting_details || "" }); setOpen(true); };
  const openIntake = (s) => { setIntakeService(s); setIntakeOpen(true); };

  const save = async (e) => {
    e.preventDefault();
    const payload = { ...form, duration_min: Number(form.duration_min), price: Number(form.price) };
    try {
      if (editing) {
        await api.put(`/me/services/${editing.id}`, payload);
        toast.success("Service updated");
      } else {
        await api.post("/me/services", payload);
        toast.success("Service added");
      }
      setOpen(false);
      load();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    }
  };

  const remove = async (s) => {
    if (!window.confirm(`Delete "${s.name}"?`)) return;
    await api.delete(`/me/services/${s.id}`);
    toast.success("Service deleted");
    load();
  };

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-heading text-4xl">Services</h1>
          <p className="text-cocoaSoft mt-1">What you offer to your clients.</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button onClick={openCreate} className="rounded-full btn-lift" data-testid="add-service-button">
              <Plus className="h-4 w-4 mr-2" /> Add service
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="font-heading text-2xl">{editing ? "Edit service" : "New service"}</DialogTitle>
            </DialogHeader>
            <form onSubmit={save} className="space-y-4 mt-2" data-testid="service-form">
              <div className="space-y-2">
                <Label>Service name</Label>
                <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required placeholder="Initial Consultation" data-testid="service-name-input" />
              </div>
              <div className="space-y-2">
                <Label>Description</Label>
                <Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="What clients get from this session…" rows={3} data-testid="service-description-input" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label>Duration (minutes)</Label>
                  <Input type="number" min={5} max={480} value={form.duration_min} onChange={(e) => setForm({ ...form, duration_min: e.target.value })} required data-testid="service-duration-input" />
                </div>
                <div className="space-y-2">
                  <Label>Price (₹)</Label>
                  <Input type="number" min={0} value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} required data-testid="service-price-input" />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Cover image URL (optional)</Label>
                <Input value={form.cover_image} onChange={(e) => setForm({ ...form, cover_image: e.target.value })} placeholder="https://…" data-testid="service-image-input" />
              </div>

              <div className="space-y-3 pt-2 border-t border-border">
                <Label>How will you meet the customer?</Label>
                <div className="grid grid-cols-3 gap-2" data-testid="meeting-mode-group">
                  {Object.entries(MODE_META).map(([key, m]) => {
                    const Icon = m.icon;
                    const active = form.meeting_mode === key;
                    return (
                      <button
                        key={key}
                        type="button"
                        onClick={() => setForm({ ...form, meeting_mode: key })}
                        className={`text-left border rounded-lg px-3 py-2.5 transition ${active ? "border-primary bg-primary/5" : "border-border hover:border-primary/40"}`}
                        data-testid={`meeting-mode-${key}`}
                      >
                        <Icon className={`h-4 w-4 ${active ? "text-primary" : "text-cocoaSoft"}`} />
                        <p className="text-sm mt-1 font-medium">{m.label}</p>
                      </button>
                    );
                  })}
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs text-cocoaSoft">
                    {form.meeting_mode === "in_person" ? "Address (default for this service)" :
                     form.meeting_mode === "phone" ? "Your phone number (optional)" :
                     "Default meeting link (optional)"}
                  </Label>
                  {form.meeting_mode === "in_person" ? (
                    <Textarea
                      value={form.meeting_details}
                      onChange={(e) => setForm({ ...form, meeting_details: e.target.value })}
                      placeholder={MODE_META[form.meeting_mode].placeholder}
                      rows={2}
                      data-testid="service-meeting-details"
                    />
                  ) : (
                    <Input
                      value={form.meeting_details}
                      onChange={(e) => setForm({ ...form, meeting_details: e.target.value })}
                      placeholder={MODE_META[form.meeting_mode].placeholder}
                      data-testid="service-meeting-details"
                    />
                  )}
                  <p className="text-[11px] text-cocoaSoft">{MODE_META[form.meeting_mode].help} You can override this per booking.</p>
                </div>
              </div>
              <DialogFooter>
                <Button type="button" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
                <Button type="submit" className="rounded-full" data-testid="service-save-button">{editing ? "Save changes" : "Add service"}</Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {services.length === 0 ? (
        <div className="paper-card p-12 text-center" data-testid="services-empty-state">
          <p className="font-heading text-3xl">Add your first service</p>
          <p className="text-cocoaSoft mt-2 max-w-md mx-auto">Define what you offer, how long it takes, and how much it costs. Clients will pick from these on your booking page.</p>
          <Button onClick={openCreate} className="rounded-full mt-6 btn-lift">
            <Plus className="h-4 w-4 mr-2" /> Add service
          </Button>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {services.map((s) => {
            const qCount = (s.intake_questions || []).length;
            return (
              <div key={s.id} className="paper-card p-5 flex flex-col" data-testid={`service-card-${s.id}`}>
                <h3 className="font-heading text-2xl leading-tight">{s.name}</h3>
                {s.description && <p className="text-sm text-cocoaSoft mt-2 line-clamp-3 flex-1">{s.description}</p>}
                <div className="flex items-center gap-4 mt-4 text-sm text-cocoaSoft flex-wrap">
                  <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> {s.duration_min} min</span>
                  <span className="flex items-center gap-1"><IndianRupee className="h-3.5 w-3.5" /> {s.price}</span>
                  {(() => {
                    const meta = MODE_META[s.meeting_mode || "video"];
                    const Icon = meta.icon;
                    return <span className="flex items-center gap-1" data-testid={`service-mode-${s.id}`}><Icon className="h-3.5 w-3.5" /> {meta.label}</span>;
                  })()}
                </div>
                <button
                  type="button"
                  onClick={() => openIntake(s)}
                  className="mt-3 text-xs flex items-center gap-1.5 text-cocoaSoft hover:text-primary self-start"
                  data-testid={`edit-intake-${s.id}`}
                >
                  <FileText className="h-3.5 w-3.5" />
                  {qCount === 0 ? "Add intake form" : `Intake form · ${qCount} question${qCount === 1 ? "" : "s"}`}
                </button>
                <div className="flex gap-2 mt-5 pt-4 border-t border-border">
                  <Button variant="outline" size="sm" onClick={() => openEdit(s)} className="flex-1" data-testid={`edit-service-${s.id}`}>
                    <Pencil className="h-3.5 w-3.5 mr-1.5" /> Edit
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => remove(s)} className="text-destructive hover:text-destructive" data-testid={`delete-service-${s.id}`}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <IntakeFormBuilder
        open={intakeOpen}
        onOpenChange={setIntakeOpen}
        service={intakeService}
        onSaved={load}
      />
    </div>
  );
}
