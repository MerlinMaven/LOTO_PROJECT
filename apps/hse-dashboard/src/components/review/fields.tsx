/**
 * Small controlled-field building blocks shared by the review panels.
 *
 * Every editable field highlights when its value differs from the supplied
 * `original`, so the reviewer always sees what they have changed. When
 * `readOnly` is true (non-draft versions) inputs are disabled.
 */

import { clsx } from "clsx";

interface BaseProps {
  label: string;
  readOnly?: boolean;
  hint?: string;
}

export function TextField({
  label,
  value,
  original,
  onCommit,
  readOnly,
  hint,
  multiline,
}: BaseProps & {
  value: string;
  original?: string;
  onCommit: (next: string) => void;
  multiline?: boolean;
}) {
  const dirty = original !== undefined && original !== value;

  const commonProps = {
    value,
    disabled: readOnly,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      onCommit(e.target.value),
    className: clsx("field-input", dirty && "field-dirty"),
  };

  return (
    <label className="block">
      <span className="field-label">{label}</span>
      {multiline ? (
        <textarea rows={2} {...commonProps} />
      ) : (
        <input type="text" {...commonProps} />
      )}
      {hint && <span className="mt-1 block text-[11px] text-steel-400">{hint}</span>}
    </label>
  );
}

export function SelectField({
  label,
  value,
  original,
  options,
  onCommit,
  readOnly,
}: BaseProps & {
  value: string;
  original?: string;
  options: { value: string; label: string }[];
  onCommit: (next: string) => void;
}) {
  const dirty = original !== undefined && original !== value;
  return (
    <label className="block">
      <span className="field-label">{label}</span>
      <select
        value={value}
        disabled={readOnly}
        onChange={(e) => onCommit(e.target.value)}
        className={clsx("field-input", dirty && "field-dirty")}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function NumberField({
  label,
  value,
  original,
  onCommit,
  readOnly,
  min = 0,
  max = 1,
  step = 0.05,
}: BaseProps & {
  value: number;
  original?: number;
  onCommit: (next: number) => void;
  min?: number;
  max?: number;
  step?: number;
}) {
  const dirty = original !== undefined && original !== value;
  return (
    <label className="block">
      <span className="field-label">{label}</span>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        disabled={readOnly}
        onChange={(e) => onCommit(Number(e.target.value))}
        className={clsx("field-input", dirty && "field-dirty")}
      />
    </label>
  );
}

/**
 * Editor for a list of short strings (YOLO prompts, warnings, etc).
 * Each line is a separate prompt; the reviewer can replace, add, or remove any.
 */
export function TagListEditor({
  label,
  values,
  original,
  onCommit,
  readOnly,
  placeholder,
}: BaseProps & {
  values: string[];
  original?: string[];
  onCommit: (next: string[]) => void;
  placeholder?: string;
}) {
  const dirty =
    original !== undefined && JSON.stringify(original) !== JSON.stringify(values);

  const update = (idx: number, text: string) => {
    const next = [...values];
    next[idx] = text;
    onCommit(next);
  };
  const remove = (idx: number) => onCommit(values.filter((_, i) => i !== idx));
  const add = () => onCommit([...values, ""]);

  return (
    <div>
      <span className={clsx("field-label", dirty && "text-draft")}>{label}</span>
      <div className="space-y-1.5">
        {values.length === 0 && (
          <p className="text-xs italic text-steel-400">No entries.</p>
        )}
        {values.map((v, i) => (
          <div key={i} className="flex items-center gap-2">
            <input
              type="text"
              value={v}
              disabled={readOnly}
              placeholder={placeholder}
              onChange={(e) => update(i, e.target.value)}
              className={clsx("field-input flex-1", dirty && "field-dirty")}
            />
            {!readOnly && (
              <button
                type="button"
                onClick={() => remove(i)}
                className="rounded px-2 py-1 text-xs text-hazard hover:bg-red-50"
                aria-label={`Remove ${label} entry ${i + 1}`}
              >
                ✕
              </button>
            )}
          </div>
        ))}
        {!readOnly && (
          <button
            type="button"
            onClick={add}
            className="rounded px-2 py-1 text-xs font-medium text-steel-600 hover:bg-steel-100"
          >
            + Add
          </button>
        )}
      </div>
    </div>
  );
}
