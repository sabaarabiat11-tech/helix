import { Search } from "lucide-react";

export default function SearchInput({ value, onChange, placeholder = "Search…", className = "" }) {
  return (
    <div className={`relative ${className}`}>
      <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-md border border-border bg-surface pl-9 pr-3 py-2 text-[13.5px] text-ink placeholder:text-faint focus:border-accent focus:outline-none transition-colors"
      />
    </div>
  );
}
