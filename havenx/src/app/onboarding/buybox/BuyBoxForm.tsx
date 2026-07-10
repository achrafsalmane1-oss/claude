"use client";

import { useState, useTransition } from "react";
import { saveMandate, type MandateInput } from "./actions";
import { IconArrowRight, IconCheck } from "@/components/icons";

const STEPS = ["Target profile", "Financials", "Fit & situation", "Your identity"];

const SITUATIONS = [
  "Retirement",
  "Succession",
  "Owner burnout",
  "Distressed",
  "Growth capital",
  "Relocation",
  "Partnership exit",
];

const INDUSTRY_SUGGESTIONS = [
  "HVAC services",
  "Commercial landscaping",
  "Dental practices",
  "Managed IT services",
  "Specialty manufacturing",
  "Logistics & freight",
];

function TagInput({
  value,
  onChange,
  placeholder,
  suggestions = [],
}: {
  value: string[];
  onChange: (v: string[]) => void;
  placeholder: string;
  suggestions?: string[];
}) {
  const [draft, setDraft] = useState("");

  const add = (tag: string) => {
    const t = tag.trim();
    if (t && !value.includes(t)) onChange([...value, t]);
    setDraft("");
  };

  return (
    <div>
      <div className="flex flex-wrap gap-2 rounded-xl border border-line bg-panel p-2 focus-within:border-green focus-within:bg-white">
        {value.map((tag) => (
          <span
            key={tag}
            className="flex items-center gap-1.5 rounded-lg bg-green-soft px-2.5 py-1 text-[13.5px] font-medium text-green-dark"
          >
            {tag}
            <button
              type="button"
              aria-label={`Remove ${tag}`}
              onClick={() => onChange(value.filter((t) => t !== tag))}
              className="text-green-dark/60 hover:text-green-dark"
            >
              ×
            </button>
          </span>
        ))}
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              add(draft);
            }
            if (e.key === "Backspace" && !draft && value.length) {
              onChange(value.slice(0, -1));
            }
          }}
          onBlur={() => draft && add(draft)}
          placeholder={value.length ? "" : placeholder}
          className="min-w-32 flex-1 bg-transparent px-1.5 py-1 text-[14.5px] text-ink outline-none placeholder:text-ink-faint"
        />
      </div>
      {suggestions.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {suggestions
            .filter((s) => !value.includes(s))
            .map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => add(s)}
                className="rounded-lg border border-line bg-white px-2.5 py-1 text-[12.5px] text-ink-soft transition hover:border-green hover:text-green-dark"
              >
                + {s}
              </button>
            ))}
        </div>
      )}
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1.5 block text-[14px] font-medium text-ink">
        {label}
        {hint && (
          <span className="ml-2 font-normal text-ink-faint">{hint}</span>
        )}
      </label>
      {children}
    </div>
  );
}

const inputCls =
  "w-full rounded-xl border border-line bg-panel px-3.5 py-2.5 text-[14.5px] text-ink outline-none transition placeholder:text-ink-faint focus:border-green focus:bg-white";

function MoneyRange({
  label,
  min,
  max,
  onMin,
  onMax,
}: {
  label: string;
  min: string;
  max: string;
  onMin: (v: string) => void;
  onMax: (v: string) => void;
}) {
  return (
    <Field label={label} hint="USD">
      <div className="flex items-center gap-3">
        <input
          type="number"
          inputMode="numeric"
          min={0}
          value={min}
          onChange={(e) => onMin(e.target.value)}
          placeholder="Min"
          className={inputCls}
        />
        <span className="text-ink-faint">—</span>
        <input
          type="number"
          inputMode="numeric"
          min={0}
          value={max}
          onChange={(e) => onMax(e.target.value)}
          placeholder="Max"
          className={inputCls}
        />
      </div>
    </Field>
  );
}

export default function BuyBoxForm({ userEmail }: { userEmail: string }) {
  const [step, setStep] = useState(0);
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const [industries, setIndustries] = useState<string[]>([]);
  const [geographies, setGeographies] = useState<string[]>([]);
  const [keywords, setKeywords] = useState<string[]>([]);
  const [revMin, setRevMin] = useState("");
  const [revMax, setRevMax] = useState("");
  const [ebMin, setEbMin] = useState("");
  const [ebMax, setEbMax] = useState("");
  const [empMin, setEmpMin] = useState("");
  const [empMax, setEmpMax] = useState("");
  const [mustHaves, setMustHaves] = useState("");
  const [exclusions, setExclusions] = useState("");
  const [situations, setSituations] = useState<string[]>([]);
  const [senderName, setSenderName] = useState("");
  const [senderCompany, setSenderCompany] = useState("");
  const [signature, setSignature] = useState("");
  const [replyTo, setReplyTo] = useState("");
  const [thesis, setThesis] = useState("");

  const stepValid = [
    industries.length > 0 && geographies.length > 0,
    true,
    true,
    senderName.trim().length > 0 && senderCompany.trim().length > 0,
  ][step];

  const num = (s: string) => (s.trim() === "" ? null : Math.round(Number(s)));

  const submit = () => {
    setError(null);
    const input: MandateInput = {
      industries,
      geographies,
      businessModelKeywords: keywords,
      revenueMinUsd: num(revMin),
      revenueMaxUsd: num(revMax),
      ebitdaMinUsd: num(ebMin),
      ebitdaMaxUsd: num(ebMax),
      employeesMin: num(empMin),
      employeesMax: num(empMax),
      mustHaves,
      hardExclusions: exclusions,
      ownerSituations: situations,
      senderName,
      senderCompany,
      senderSignature: signature,
      senderReplyToName: replyTo,
      thesis,
    };
    startTransition(async () => {
      try {
        await saveMandate(input);
      } catch (e) {
        // redirect() throws internally — anything else is a real error
        if (e instanceof Error && e.message.includes("NEXT_REDIRECT")) throw e;
        setError("Something went wrong saving your buy-box. Please try again.");
      }
    });
  };

  return (
    <div className="w-full max-w-2xl">
      {/* Stepper */}
      <div className="mb-8 flex items-center gap-2">
        {STEPS.map((label, i) => (
          <div key={label} className="flex flex-1 flex-col gap-2">
            <div
              className={`h-1 rounded-full ${
                i <= step ? "bg-green" : "bg-line"
              }`}
            />
            <span
              className={`text-[12px] ${
                i === step
                  ? "font-semibold text-green-dark"
                  : i < step
                    ? "text-ink-soft"
                    : "text-ink-faint"
              }`}
            >
              {label}
            </span>
          </div>
        ))}
      </div>

      <div className="rounded-[24px] border border-line bg-white p-7 shadow-[0_24px_50px_-36px_rgba(30,60,40,0.5)] sm:p-9">
        {step === 0 && (
          <div className="space-y-6">
            <div>
              <h2 className="display text-[30px] text-ink">
                What are you buying?
              </h2>
              <p className="mt-1 text-[14.5px] text-ink-soft">
                We source only companies inside this profile.
              </p>
            </div>
            <Field label="Target industries / niches" hint="press Enter to add">
              <TagInput
                value={industries}
                onChange={setIndustries}
                placeholder="e.g. HVAC services, dental practices…"
                suggestions={INDUSTRY_SUGGESTIONS}
              />
            </Field>
            <Field label="Geography" hint="countries, regions, or states">
              <TagInput
                value={geographies}
                onChange={setGeographies}
                placeholder="e.g. United States, Texas, Southeast…"
              />
            </Field>
            <Field label="Business model keywords" hint="optional">
              <TagInput
                value={keywords}
                onChange={setKeywords}
                placeholder="e.g. recurring revenue, B2B, route-based…"
              />
            </Field>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-6">
            <div>
              <h2 className="display text-[30px] text-ink">Size of the prize</h2>
              <p className="mt-1 text-[14.5px] text-ink-soft">
                Leave anything blank if it&apos;s not a constraint.
              </p>
            </div>
            <MoneyRange
              label="Annual revenue"
              min={revMin}
              max={revMax}
              onMin={setRevMin}
              onMax={setRevMax}
            />
            <MoneyRange
              label="EBITDA"
              min={ebMin}
              max={ebMax}
              onMin={setEbMin}
              onMax={setEbMax}
            />
            <Field label="Employee count">
              <div className="flex items-center gap-3">
                <input
                  type="number"
                  min={0}
                  value={empMin}
                  onChange={(e) => setEmpMin(e.target.value)}
                  placeholder="Min"
                  className={inputCls}
                />
                <span className="text-ink-faint">—</span>
                <input
                  type="number"
                  min={0}
                  value={empMax}
                  onChange={(e) => setEmpMax(e.target.value)}
                  placeholder="Max"
                  className={inputCls}
                />
              </div>
            </Field>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-6">
            <div>
              <h2 className="display text-[30px] text-ink">
                What makes a fit?
              </h2>
              <p className="mt-1 text-[14.5px] text-ink-soft">
                Sharp exclusions save everyone time.
              </p>
            </div>
            <Field label="Ideal owner situation" hint="select all that apply">
              <div className="flex flex-wrap gap-2">
                {SITUATIONS.map((s) => {
                  const active = situations.includes(s);
                  return (
                    <button
                      key={s}
                      type="button"
                      onClick={() =>
                        setSituations(
                          active
                            ? situations.filter((x) => x !== s)
                            : [...situations, s]
                        )
                      }
                      className={`flex items-center gap-1.5 rounded-xl border px-3.5 py-2 text-[13.5px] font-medium transition ${
                        active
                          ? "border-green bg-green-soft text-green-dark"
                          : "border-line bg-white text-ink-soft hover:border-ink-faint"
                      }`}
                    >
                      {active && <IconCheck className="h-3.5 w-3.5" />}
                      {s}
                    </button>
                  );
                })}
              </div>
            </Field>
            <Field label="Must-haves" hint="optional">
              <textarea
                value={mustHaves}
                onChange={(e) => setMustHaves(e.target.value)}
                rows={3}
                placeholder="e.g. second layer of management in place, 60%+ recurring revenue…"
                className={inputCls}
              />
            </Field>
            <Field label="Hard exclusions" hint="optional">
              <textarea
                value={exclusions}
                onChange={(e) => setExclusions(e.target.value)}
                rows={3}
                placeholder="e.g. no franchises, no single-customer concentration above 40%…"
                className={inputCls}
              />
            </Field>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-6">
            <div>
              <h2 className="display text-[30px] text-ink">
                Who does the reaching out?
              </h2>
              <p className="mt-1 text-[14.5px] text-ink-soft">
                All outreach runs under this identity — owners see your brand,
                not ours.
              </p>
            </div>
            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Your name">
                <input
                  value={senderName}
                  onChange={(e) => setSenderName(e.target.value)}
                  placeholder="Alex Morgan"
                  className={inputCls}
                />
              </Field>
              <Field label="Company / fund">
                <input
                  value={senderCompany}
                  onChange={(e) => setSenderCompany(e.target.value)}
                  placeholder="Morgan Capital Partners"
                  className={inputCls}
                />
              </Field>
            </div>
            <Field label="Reply-to display name" hint="optional">
              <input
                value={replyTo}
                onChange={(e) => setReplyTo(e.target.value)}
                placeholder="Alex Morgan — Morgan Capital"
                className={inputCls}
              />
            </Field>
            <Field label="Signature" hint="optional">
              <textarea
                value={signature}
                onChange={(e) => setSignature(e.target.value)}
                rows={3}
                placeholder={"Alex Morgan\nManaging Partner, Morgan Capital Partners"}
                className={inputCls}
              />
            </Field>
            <Field label="Your thesis in a sentence or two" hint="optional">
              <textarea
                value={thesis}
                onChange={(e) => setThesis(e.target.value)}
                rows={3}
                placeholder="Buying founder-led B2B services companies in Texas with $500K–$1.5M EBITDA, where the owner wants a respectful exit."
                className={inputCls}
              />
            </Field>
            <p className="text-[12.5px] text-ink-faint">
              Signed in as {userEmail}
            </p>
          </div>
        )}

        {error && (
          <p className="mt-5 rounded-xl bg-fall/10 px-4 py-3 text-[13.5px] text-fall">
            {error}
          </p>
        )}

        <div className="mt-8 flex items-center justify-between border-t border-line-soft pt-6">
          <button
            type="button"
            onClick={() => setStep(Math.max(0, step - 1))}
            className={`rounded-xl px-4 py-2.5 text-[14.5px] font-medium text-ink-soft transition hover:text-ink ${
              step === 0 ? "invisible" : ""
            }`}
          >
            Back
          </button>
          {step < STEPS.length - 1 ? (
            <button
              type="button"
              disabled={!stepValid}
              onClick={() => setStep(step + 1)}
              className="flex items-center gap-2 rounded-2xl bg-ink px-6 py-3 text-[15px] font-semibold text-white transition hover:bg-black disabled:cursor-not-allowed disabled:opacity-40"
            >
              Continue
              <IconArrowRight className="h-4 w-4" />
            </button>
          ) : (
            <button
              type="button"
              disabled={!stepValid || pending}
              onClick={submit}
              className="flex items-center gap-2 rounded-2xl bg-green px-6 py-3 text-[15px] font-semibold text-white transition hover:bg-green-deep disabled:cursor-not-allowed disabled:opacity-40"
            >
              {pending ? "Activating…" : "Activate my buy-box"}
              <IconArrowRight className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
