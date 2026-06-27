import React from "react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

/**
 * Renders intake questions and collects answers.
 * Props:
 *   questions: [{id, text, type, required, options}]
 *   answers: { [question_id]: string }
 *   onChange: (question_id, value) => void
 *   testidPrefix: string
 */
export default function IntakeFormRenderer({ questions, answers, onChange, testidPrefix = "intake" }) {
  return (
    <div className="space-y-5" data-testid={`${testidPrefix}-form`}>
      {questions.map((q) => {
        const val = answers[q.id] ?? "";
        const label = (
          <Label className="flex items-center gap-1">
            {q.text}
            {q.required && <span className="text-primary" aria-label="required">*</span>}
          </Label>
        );
        const tid = `${testidPrefix}-q-${q.id}`;
        if (q.type === "long_text") {
          return (
            <div className="space-y-2" key={q.id}>
              {label}
              <Textarea rows={3} value={val} onChange={(e) => onChange(q.id, e.target.value)} data-testid={tid} />
            </div>
          );
        }
        if (q.type === "dropdown") {
          return (
            <div className="space-y-2" key={q.id}>
              {label}
              <Select value={val || undefined} onValueChange={(v) => onChange(q.id, v)}>
                <SelectTrigger data-testid={tid}><SelectValue placeholder="Choose…" /></SelectTrigger>
                <SelectContent>
                  {q.options.map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          );
        }
        const inputType = q.type === "email" ? "email" : q.type === "phone" ? "tel" : q.type === "url" ? "url" : "text";
        return (
          <div className="space-y-2" key={q.id}>
            {label}
            <Input
              type={inputType}
              value={val}
              onChange={(e) => onChange(q.id, e.target.value)}
              placeholder={q.type === "url" ? "https://…" : ""}
              data-testid={tid}
            />
          </div>
        );
      })}
    </div>
  );
}

/**
 * Returns array of {field, message} for missing required answers / invalid format.
 */
export function validateIntakeAnswers(questions, answers) {
  const errors = [];
  const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
  const URL_RE = /^https?:\/\//i;
  for (const q of questions) {
    const v = (answers[q.id] ?? "").trim();
    if (q.required && !v) {
      errors.push({ field: q.text, message: "Required" });
      continue;
    }
    if (!v) continue;
    if (q.type === "email" && !EMAIL_RE.test(v)) errors.push({ field: q.text, message: "Invalid email" });
    if (q.type === "url" && !URL_RE.test(v)) errors.push({ field: q.text, message: "Must start with http:// or https://" });
    if (q.type === "phone" && v.replace(/\D/g, "").length < 6) errors.push({ field: q.text, message: "Invalid phone" });
  }
  return errors;
}
