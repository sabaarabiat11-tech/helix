import { useEffect, useState } from "react";
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { api } from "../api/client";
import { useRun } from "../hooks/RunContext";
import { useChartColors } from "../hooks/useChartColors";
import PageShell from "../components/PageShell";
import ChartCard from "../components/ChartCard";
import ScanLoader from "../components/ScanLoader";
import Heatmap from "../components/Heatmap";

function tooltipStyle(colors) {
  return {
    background: colors.surface,
    border: `1px solid ${colors.border}`,
    borderRadius: 8,
    fontSize: 12.5,
    color: colors.text,
  };
}

export default function Analytics() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const { refreshKey } = useRun();
  const colors = useChartColors();

  useEffect(() => {
    let cancelled = false;
    api
      .analytics()
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  if (error) {
    return (
      <PageShell title="Analytics" subtitle="Trends across the discovery database">
        <div className="rounded-md border border-danger/30 bg-danger-soft text-danger text-[13px] px-4 py-3">
          {error}
        </div>
      </PageShell>
    );
  }

  if (!data) {
    return (
      <PageShell title="Analytics" subtitle="Trends across the discovery database">
        <div className="flex items-center gap-2 justify-center text-dim py-12">
          <ScanLoader size={20} /> Loading analytics…
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell title="Analytics" subtitle="Trends across the discovery database">
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <ChartCard title="Discoveries Over Time" subtitle="New people added, by day" className="xl:col-span-2">
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={data.discoveries_over_time} margin={{ left: -20, right: 10 }}>
              <defs>
                <linearGradient id="fillDiscoveries" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={colors.accent} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={colors.accent} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={colors.border} strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: colors["text-faint"] }} tickLine={false} axisLine={{ stroke: colors.border }} />
              <YAxis tick={{ fontSize: 11, fill: colors["text-faint"] }} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle(colors)} />
              <Legend wrapperStyle={{ fontSize: 11.5, color: colors["text-dim"] }} />
              <Area type="monotone" dataKey="count" name="New people" stroke={colors.accent} strokeWidth={2} fill="url(#fillDiscoveries)" />
              <Line
                type="monotone"
                dataKey="moving_avg"
                name="7-day moving average"
                stroke={colors["accent-2"]}
                strokeWidth={2}
                strokeDasharray="4 3"
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Company Growth" subtitle="Cumulative discoveries over time, top 6 companies" className="xl:col-span-2">
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={data.company_growth} margin={{ left: -20, right: 10 }}>
              <CartesianGrid stroke={colors.border} strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: colors["text-faint"] }} tickLine={false} axisLine={{ stroke: colors.border }} />
              <YAxis tick={{ fontSize: 11, fill: colors["text-faint"] }} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle(colors)} />
              <Legend wrapperStyle={{ fontSize: 11, color: colors["text-dim"] }} />
              {data.company_growth_keys.map((company, i) => (
                <Line
                  key={company}
                  type="monotone"
                  dataKey={company}
                  stroke={colors.series[i % colors.series.length]}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Top Companies" subtitle="By total people discovered">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={data.top_companies} layout="vertical" margin={{ left: 10, right: 10 }}>
              <CartesianGrid stroke={colors.border} strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11, fill: colors["text-faint"] }} tickLine={false} axisLine={{ stroke: colors.border }} allowDecimals={false} />
              <YAxis type="category" dataKey="company" width={140} tick={{ fontSize: 11, fill: colors["text-dim"] }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={tooltipStyle(colors)} cursor={{ fill: colors["surface-2"] }} />
              <Bar dataKey="count" name="People" fill={colors.accent} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Top Roles" subtitle="Grouped by role category">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={data.top_roles} layout="vertical" margin={{ left: 10, right: 10 }}>
              <CartesianGrid stroke={colors.border} strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11, fill: colors["text-faint"] }} tickLine={false} axisLine={{ stroke: colors.border }} allowDecimals={false} />
              <YAxis type="category" dataKey="role" width={170} tick={{ fontSize: 11, fill: colors["text-dim"] }} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={tooltipStyle(colors)} cursor={{ fill: colors["surface-2"] }} />
              <Bar dataKey="count" name="People" fill={colors["accent-2"]} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Source Contribution" subtitle="Where each person was found">
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={data.source_contribution}
                dataKey="count"
                nameKey="source"
                innerRadius={55}
                outerRadius={95}
                paddingAngle={2}
                stroke={colors.surface}
              >
                {data.source_contribution.map((_, i) => (
                  <Cell key={i} fill={colors.series[i % colors.series.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={tooltipStyle(colors)} />
              <Legend wrapperStyle={{ fontSize: 11.5, color: colors["text-dim"] }} />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Weekly Growth" subtitle="New per week vs. cumulative total" className="xl:col-span-2">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={data.weekly_growth} margin={{ left: -20, right: 10 }}>
              <CartesianGrid stroke={colors.border} strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="week" tick={{ fontSize: 11, fill: colors["text-faint"] }} tickLine={false} axisLine={{ stroke: colors.border }} />
              <YAxis tick={{ fontSize: 11, fill: colors["text-faint"] }} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip contentStyle={tooltipStyle(colors)} />
              <Legend wrapperStyle={{ fontSize: 11.5, color: colors["text-dim"] }} />
              <Line type="monotone" dataKey="new" name="New this week" stroke={colors["accent-2"]} strokeWidth={2} dot={{ r: 3 }} />
              <Line type="monotone" dataKey="cumulative" name="Cumulative total" stroke={colors.accent} strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Discovery Heatmap" subtitle="Top companies × source, intensity = people found" className="xl:col-span-2">
          <Heatmap data={data.heatmap} sources={data.heatmap_sources} colors={colors} />
        </ChartCard>
      </div>
    </PageShell>
  );
}
