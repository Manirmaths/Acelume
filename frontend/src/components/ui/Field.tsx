import type { ReactNode } from 'react';

/**
 * A labelled form field.
 *
 * Exists because the first version of the exam builder used placeholders
 * alone, and a placeholder disappears the moment you type into it. Someone
 * setting up a real exam looks back at a row of boxes containing "3", "20"
 * and "60" with nothing to say which is which — and gets the duration wrong.
 *
 * A visible label survives being filled in. The hint sits underneath for the
 * things a label cannot carry, like units or what a field is actually for.
 */
export default function Field({
  label,
  hint,
  htmlFor,
  children,
  className = '',
}: {
  label: string;
  hint?: string;
  htmlFor?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <label htmlFor={htmlFor} className="block text-sm font-semibold text-ink-800 mb-1">
        {label}
      </label>
      {children}
      {hint && <p className="text-xs text-ink-400 mt-1 leading-snug">{hint}</p>}
    </div>
  );
}

export function TextInput({
  id,
  value,
  onChange,
  placeholder,
  type = 'text',
  min,
  max,
}: {
  id?: string;
  value: string | number;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: string;
  min?: number;
  max?: number;
}) {
  return (
    <input
      id={id}
      type={type}
      value={value}
      min={min}
      max={max}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-xl border border-ink-200 px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-200"
    />
  );
}
