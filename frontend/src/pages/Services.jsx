import React, { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { Plus, Pencil, Trash2, Clock, IndianRupee } from "lucide-react";
import { toast } from "sonner";

const emptyForm = { name: "", description: "", duration_min: 60, price: 1000, cover_image: "" };

export default function Services() {
  const [services, setServices] = useState([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);

  const load = async () => {
    const { data } = await api.get("/me/services");
    setServices(data);
  };
  useEffect(() => { load(); }, []);

  const openCreate = () => { setEditing(null); setForm(emptyForm); setOpen(true); };
  const openEdit = (s) => { setEditing(s); setForm({ name: s.name, description: s.description, duration_min: s.duration_min, price: s.price, cover_image: s.cover_image || "" }); setOpen(true); };

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
          {services.map((s) => (
            <div key={s.id} className="paper-card p-5 flex flex-col" data-testid={`service-card-${s.id}`}>
              <h3 className="font-heading text-2xl leading-tight">{s.name}</h3>
              {s.description && <p className="text-sm text-cocoaSoft mt-2 line-clamp-3 flex-1">{s.description}</p>}
              <div className="flex items-center gap-4 mt-4 text-sm text-cocoaSoft">
                <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> {s.duration_min} min</span>
                <span className="flex items-center gap-1"><IndianRupee className="h-3.5 w-3.5" /> {s.price}</span>
              </div>
              <div className="flex gap-2 mt-5 pt-4 border-t border-border">
                <Button variant="outline" size="sm" onClick={() => openEdit(s)} className="flex-1" data-testid={`edit-service-${s.id}`}>
                  <Pencil className="h-3.5 w-3.5 mr-1.5" /> Edit
                </Button>
                <Button variant="ghost" size="sm" onClick={() => remove(s)} className="text-destructive hover:text-destructive" data-testid={`delete-service-${s.id}`}>
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
