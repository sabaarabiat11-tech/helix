import { Fragment } from "react";
import Tooltip from "./ui/Tooltip";

/** Simple CSS-grid heatmap: rows = companies, columns = sources, cell
 * opacity scales with count. Recharts has no native heatmap primitive, and
 * a plain grid reads more clearly than forcing a scatter/treemap here. */
export default function Heatmap({ data, sources, colors }) {
  if (!data || data.length === 0) {
    return <p className="text-[12.5px] text-faint py-8 text-center">No data yet.</p>;
  }

  const companies = [...new Set(data.map((d) => d.company))];
  const maxCount = Math.max(1, ...data.map((d) => d.count));
  const byKey = Object.fromEntries(data.map((d) => [`${d.company}::${d.source}`, d.count]));

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[520px]">
        <div
          className="grid gap-1"
          style={{ gridTemplateColumns: `140px repeat(${sources.length}, minmax(70px, 1fr))` }}
        >
          <div />
          {sources.map((s) => (
            <div key={s} className="text-[10.5px] text-faint text-center pb-1.5 truncate" title={s}>
              {s}
            </div>
          ))}
          {companies.map((company) => (
            <Fragment key={company}>
              <div className="text-[12px] text-dim truncate pr-2 flex items-center" title={company}>
                {company}
              </div>
              {sources.map((source) => {
                const count = byKey[`${company}::${source}`] ?? 0;
                const intensity = count / maxCount;
                return (
                  <Tooltip key={`${company}-${source}`} content={`${company} × ${source}: ${count}`}>
                    <div
                      className="aspect-square rounded-md flex items-center justify-center text-[11px] font-mono tabular-nums cursor-default"
                      style={{
                        background: intensity === 0 ? colors["surface-2"] : colors.accent,
                        opacity: intensity === 0 ? 1 : 0.15 + intensity * 0.85,
                        color: intensity > 0.45 ? "#04121f" : colors["text-faint"],
                      }}
                    >
                      {count > 0 ? count : ""}
                    </div>
                  </Tooltip>
                );
              })}
            </Fragment>
          ))}
        </div>
      </div>
    </div>
  );
}
