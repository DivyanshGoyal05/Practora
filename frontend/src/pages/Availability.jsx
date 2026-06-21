import React, { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover";
import { toast } from "sonner";
import { CalendarIcon, X } from "lucide-react";

const DAYS = [
  { key: "mon", label: "Monday" },
  { key: "tue", label: "Tuesday" },
  { key: "wed", label: "Wednesday" },
  { key: "thu", label: "Thursday" },
  { key: "fri", label: "Friday" },
  { key: "sat", label: "Saturday" },
  { key: "sun", label: "Sunday" },
];

export default function Availability() {
  const [schedule, setSchedule] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get("/me/schedule").then((r) => setSchedule(r.data));
  }, []);

  const update = (key, patch) => setSchedule((s) => ({ ...s, days: { ...s.days, [key]: { ...s.days[key], ...patch } } }));

  const addBlockedDate = (d) => {
    if (!d) return;
    const iso = d.toISOString().slice(0, 10);
    if (schedule.blocked_dates.includes(iso)) return;
    setSchedule((s) => ({ ...s, blocked_dates: [...s.blocked_dates, iso].sort() }));
  };
  const removeBlockedDate = (iso) => setSchedule((s) => ({ ...s, blocked_dates: s.blocked_dates.filter((x) => x !== iso) }));

  const save = async () => {
    setSaving(true);
    try {
      await api.put("/me/schedule", {
        days: schedule.days,
        buffer_min: Number(schedule.buffer_min),
        blocked_dates: schedule.blocked_dates,
      });
      toast.success("Availability saved");
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  if (!schedule) return <div className="text-cocoaSoft">Loading…</div>;

  return (
    <div className="space-y-8 animate-fade-up">
      <div>
        <h1 className="font-heading text-4xl">Availability</h1>
        <p className="text-cocoaSoft mt-1">Set your hours, buffer time, and dates off.</p>
      </div>

      <div className="paper-card divide-y divide-border" data-testid="weekly-schedule">
        {DAYS.map((d) => {
          const day = schedule.days[d.key] || { enabled: false, start: "09:00", end: "18:00" };
          return (
            <div key={d.key} className="p-4 md:p-5 grid grid-cols-12 items-center gap-3" data-testid={`schedule-row-${d.key}`}>
              <div className="col-span-12 md:col-span-3 flex items-center gap-3">
                <Switch checked={day.enabled} onCheckedChange={(v) => update(d.key, { enabled: v })} data-testid={`day-toggle-${d.key}`} />
                <span className={`font-medium ${day.enabled ? "" : "text-cocoaSoft"}`}>{d.label}</span>
              </div>
              <div className="col-span-12 md:col-span-9 flex flex-wrap items-center gap-3">
                <Input type="time" value={day.start} onChange={(e) => update(d.key, { start: e.target.value })} disabled={!day.enabled} className="w-32" data-testid={`day-start-${d.key}`} />
                <span className="text-cocoaSoft text-sm">to</span>
                <Input type="time" value={day.end} onChange={(e) => update(d.key, { end: e.target.value })} disabled={!day.enabled} className="w-32" data-testid={`day-end-${d.key}`} />
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="paper-card p-5">
          <h3 className="font-heading text-2xl">Buffer time</h3>
          <p className="text-sm text-cocoaSoft mt-1">Breathing room between sessions.</p>
          <div className="mt-4 flex items-center gap-3">
            <Input type="number" min={0} max={120} value={schedule.buffer_min} onChange={(e) => setSchedule((s) => ({ ...s, buffer_min: e.target.value }))} className="w-28" data-testid="buffer-input" />
            <span className="text-sm text-cocoaSoft">minutes</span>
          </div>
        </div>

        <div className="paper-card p-5">
          <h3 className="font-heading text-2xl">Blocked dates</h3>
          <p className="text-sm text-cocoaSoft mt-1">Holidays, travel, days off.</p>
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="outline" size="sm" className="mt-3" data-testid="add-blocked-date-button">
                <CalendarIcon className="h-4 w-4 mr-2" /> Add date
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0">
              <Calendar mode="single" onSelect={addBlockedDate} disabled={(d) => d < new Date(new Date().setHours(0,0,0,0))} />
            </PopoverContent>
          </Popover>
          <div className="mt-4 flex flex-wrap gap-2" data-testid="blocked-dates-list">
            {schedule.blocked_dates.length === 0 ? (
              <p className="text-sm text-cocoaSoft">No blocked dates.</p>
            ) : (
              schedule.blocked_dates.map((d) => (
                <span key={d} className="inline-flex items-center gap-1 text-xs bg-secondary text-foreground px-2 py-1 rounded-full">
                  {d}
                  <button onClick={() => removeBlockedDate(d)} className="hover:text-destructive" data-testid={`remove-blocked-${d}`}>
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="flex justify-end">
        <Button onClick={save} disabled={saving} className="rounded-full btn-lift" data-testid="save-availability-button">
          {saving ? "Saving…" : "Save availability"}
        </Button>
      </div>
    </div>
  );
}
