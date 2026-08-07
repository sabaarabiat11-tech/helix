export default function ChartCard({ title, subtitle, children, className = "" }) {
  return (
    <div className={`rounded-lg border border-border bg-surface p-5 ${className}`}>
      <div className="mb-4">
        <div className="text-[13.5px] font-semibold text-ink">{title}</div>
        {subtitle && <div className="text-[12px] text-faint mt-0.5">{subtitle}</div>}
      </div>
      {children}
    </div>
  );
}
