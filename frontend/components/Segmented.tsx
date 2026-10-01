"use client";

interface Option<T> {
  value: T;
  label: string;
  hint?: string;
}

interface Props<T> {
  label: string;
  value: T;
  options: Option<T>[];
  onChange: (value: T) => void;
  disabled?: boolean;
}

/** Accessible segmented control built on a radio group. */
export function Segmented<T extends string | number>({
  label,
  value,
  options,
  onChange,
  disabled,
}: Props<T>) {
  const name = label.toLowerCase().replace(/\s+/g, "-");
  return (
    <fieldset className="flex flex-col gap-2" disabled={disabled}>
      <legend className="mb-2 text-sm font-medium text-zinc-300">{label}</legend>
      <div className="grid auto-cols-fr grid-flow-col gap-1 rounded-xl border border-zinc-800 bg-zinc-900 p-1">
        {options.map((option) => {
          const checked = option.value === value;
          return (
            <label
              key={String(option.value)}
              className={`cursor-pointer rounded-lg px-3 py-2 text-center text-sm transition has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-orange-400 ${
                checked
                  ? "bg-orange-500 font-semibold text-zinc-950"
                  : "text-zinc-300 hover:bg-zinc-800"
              }`}
            >
              <input
                type="radio"
                name={name}
                value={String(option.value)}
                checked={checked}
                onChange={() => onChange(option.value)}
                className="sr-only"
              />
              {option.label}
              {option.hint && (
                <span
                  className={`block text-[11px] ${checked ? "text-zinc-900/70" : "text-zinc-500"}`}
                >
                  {option.hint}
                </span>
              )}
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
