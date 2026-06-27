import React, { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Plus, Trash2, ArrowUp, ArrowDown, GripVertical } from "lucide-react";
import { toast } from "sonner";

const TYPE_OPTIONS = [
  { value: "short_text", label: "Short text" },
  { value: "long_text", label: "Long text" },
  { value: "dropdown", label: "Dropdown" },
  { value: "email", label: "Email" },
  { value: "phone", label: "Phone" },
  { value: "url", label: "URL" },
];

const newQuestion = () => ({
  id: (typeof crypto !== "undefined" && crypto.randomUUID) ? crypto.randomUUID() : Math.random().toString(36).slice(2),
  text: "",
  type: "short_text",
  required: false,
  options: [],
  _new: true,
});

export default function IntakeFormBuilder({ open, onOpenChange, service, onSaved }) {
  const [questions, setQuestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open || !service) return;
    setLoading(true);
    api.get(`/me/services/${service.id}/intake-form`)
      .then((r) => setQuestions(r.data.questions || []))
      .finally(() => setLoading(false));
  }, [open, service]);

  const add = () => {
    if (questions.length >= 20) {
      toast.error("Max 20 questions per service");
      return;
    }
    setQuestions((q) => [...q, newQuestion()]);
  };
  const patch = (idx, p) => setQuestions((q) => q.map((it, i) => (i === idx ? { ...it, ...p } : it)));
  const remove = (idx) => setQuestions((q) => q.filter((_, i) => i !== idx));
  const move = (idx, dir) => {
    setQuestions((q) => {
      const n = [...q];
      const j = idx + dir;
      if (j < 0 || j >= n.length) return n;
      [n[idx], n[j]] = [n[j], n[idx]];
      return n;
    });
  };

  const save = async () => {
    // Client-side validation
    for (const q of questions) {
      if (!q.text.trim()) { toast.error("Every question needs text"); return; }
      if (q.type === "dropdown" && (!q.options || q.options.filter((o) => o.trim()).length === 0)) {
        toast.error(`Dropdown "${q.text}" needs at least one option`); return;
      }
    }
    setSaving(true);
    try {
      const payload = {
        questions: questions.map((q) => ({
          id: q._new ? null : q.id,
          text: q.text.trim(),
          type: q.type,
          required: !!q.required,
          options: q.type === "dropdown" ? q.options.filter((o) => o.trim()) : [],
        })),
      };
      await api.put(`/me/services/${service.id}/intake-form`, payload);
      toast.success("Intake form saved");
      onOpenChange(false);
      onSaved && onSaved(payload.questions.length);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="font-heading text-2xl">Intake form — {service?.name}</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-cocoaSoft">Questions clients answer when booking this service. Snapshots are saved on each booking, so editing later won't change past answers.</p>

        <div className="flex-1 overflow-y-auto -mx-6 px-6 mt-2 space-y-3" data-testid="intake-builder-list">
          {loading && <p className="text-cocoaSoft text-sm">Loading…</p>}
          {!loading && questions.length === 0 && (
            <div className="paper-card p-8 text-center" data-testid="intake-builder-empty">
              <p className="font-heading text-2xl">No questions yet</p>
              <p className="text-cocoaSoft text-sm mt-1">Add a few to gather info before the session.</p>
            </div>
          )}
          {questions.map((q, idx) => (
            <div key={q.id} className="paper-card p-4 space-y-3" data-testid={`question-card-${idx}`}>
              <div className="flex items-start gap-2">
                <div className="flex flex-col gap-1 pt-1">
                  <button type="button" onClick={() => move(idx, -1)} disabled={idx === 0} className="text-cocoaSoft hover:text-primary disabled:opacity-30" data-testid={`question-up-${idx}`}><ArrowUp className="h-4 w-4" /></button>
                  <GripVertical className="h-4 w-4 text-cocoaSoft/40" />
                  <button type="button" onClick={() => move(idx, 1)} disabled={idx === questions.length - 1} className="text-cocoaSoft hover:text-primary disabled:opacity-30" data-testid={`question-down-${idx}`}><ArrowDown className="h-4 w-4" /></button>
                </div>
                <div className="flex-1 space-y-3">
                  <Input
                    value={q.text}
                    onChange={(e) => patch(idx, { text: e.target.value })}
                    placeholder="Question text"
                    data-testid={`question-text-${idx}`}
                  />
                  <div className="flex flex-wrap items-center gap-3">
                    <Select value={q.type} onValueChange={(v) => patch(idx, { type: v, options: v === "dropdown" ? (q.options.length ? q.options : [""]) : [] })}>
                      <SelectTrigger className="w-44" data-testid={`question-type-${idx}`}><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {TYPE_OPTIONS.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                      </SelectContent>
                    </Select>
                    <label className="flex items-center gap-2 text-sm text-cocoaSoft cursor-pointer">
                      <Switch checked={q.required} onCheckedChange={(v) => patch(idx, { required: v })} data-testid={`question-required-${idx}`} />
                      Required
                    </label>
                  </div>
                  {q.type === "dropdown" && (
                    <div className="space-y-2 pl-1" data-testid={`dropdown-options-${idx}`}>
                      <p className="text-xs uppercase tracking-[0.15em] text-cocoaSoft">Options</p>
                      {(q.options.length ? q.options : [""]).map((opt, oi) => (
                        <div key={oi} className="flex items-center gap-2">
                          <Input
                            value={opt}
                            onChange={(e) => {
                              const next = [...(q.options.length ? q.options : [""])];
                              next[oi] = e.target.value;
                              patch(idx, { options: next });
                            }}
                            placeholder={`Option ${oi + 1}`}
                            data-testid={`dropdown-option-${idx}-${oi}`}
                          />
                          <button type="button" onClick={() => patch(idx, { options: q.options.filter((_, i) => i !== oi) })} className="text-cocoaSoft hover:text-destructive"><Trash2 className="h-4 w-4" /></button>
                        </div>
                      ))}
                      <Button type="button" size="sm" variant="ghost" onClick={() => patch(idx, { options: [...(q.options || []), ""] })} data-testid={`add-option-${idx}`}>
                        <Plus className="h-3 w-3 mr-1" /> Add option
                      </Button>
                    </div>
                  )}
                </div>
                <button type="button" onClick={() => remove(idx)} className="text-cocoaSoft hover:text-destructive p-1" data-testid={`question-delete-${idx}`}>
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
          {!loading && (
            <Button type="button" variant="outline" onClick={add} className="w-full rounded-full mt-3" data-testid="add-question-button">
              <Plus className="h-4 w-4 mr-2" /> Add question
            </Button>
          )}
        </div>

        <DialogFooter className="border-t border-border pt-4 mt-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={save} disabled={saving} className="rounded-full" data-testid="save-intake-button">
            {saving ? "Saving…" : "Save form"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
