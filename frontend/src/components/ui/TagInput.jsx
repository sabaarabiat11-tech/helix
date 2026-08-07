import { useId, useState } from "react";
import { X } from "lucide-react";
import { cn } from "../../lib/cn";

/**
 * Free-text list editor for preference fields (focus areas, companies,
 * locations).
 *
 * Commits on Enter, comma, or blur — blur matters because users routinely type
 * a value and click elsewhere expecting it to stick. Backspace on an empty
 * input removes the last chip, the convention every tag field shares.
 */
export default function TagInput({ label, hint, placeholder, value = [], onChange, disabled }) {
  const [draft, setDraft] = useState("");
  const id = useId();

  function commit(raw) {
    const entry = raw.trim();
    if (!entry) return;
    // Case-insensitive duplicate check, but keep the casing the user typed.
    const exists = value.some((v) => v.toLowerCase() === entry.toLowerCase());
    if (!exists) onChange([...value, entry]);
    setDraft("");
  }

  function remove(index) {
    onChange(value.filter((_, i) => i !== index));
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      commit(draft);
    } else if (event.key === "Backspace" && !draft && value.length) {
      remove(value.length - 1);
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[12.5px] font-medium text-dim">{label}</label>

      <div
        className={cn(
          "flex flex-wrap items-center gap-1.5 rounded-md border border-border bg-surface px-2 py-2",
          "focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/30 transition-colors",
          disabled && "opacity-50 pointer-events-none"
        )}
      >
        {value.map((tag, index) => (
          <span
            key={`${tag}-${index}`}
            className="inline-flex items-center gap-1.5 rounded-md bg-accent-soft border border-accent/25 pl-2.5 pr-1.5 py-1 text-[12px] text-accent"
          >
            {tag}
            <button
              type="button"
              onClick={() => remove(index)}
              aria-label={`Remove ${tag}`}
              className="rounded hover:bg-accent/20 p-0.5 transition-colors"
            >
              <X size={11} />
            </button>
          </span>
        ))}

        <input
          id={id}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => commit(draft)}
          placeholder={value.length ? "" : placeholder}
          disabled={disabled}
          className="flex-1 min-w-[140px] bg-transparent px-1 py-0.5 text-[13px] text-ink placeholder:text-faint focus:outline-none"
        />
      </div>

      {hint && <p className="text-[11.5px] text-faint">{hint}</p>}
    </div>
  );
}
