import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, ExternalLink, Users } from "lucide-react";
import { createColumnHelper } from "@tanstack/react-table";
import { api } from "../api/client";
import { useRun } from "../hooks/RunContext";
import PageShell from "../components/PageShell";
import SourceBadge from "../components/SourceBadge";
import FollowButton from "../components/FollowButton";
import DataTable from "../components/ui/DataTable";
import Card from "../components/ui/Card";
import ScanLoader from "../components/ScanLoader";
import { formatDate } from "../lib/format";

const columnHelper = createColumnHelper();

const columns = [
  columnHelper.accessor("name", {
    header: "Name",
    cell: (info) => <span className="font-medium text-ink whitespace-nowrap">{info.getValue()}</span>,
  }),
  columnHelper.accessor("title", {
    header: "Title",
    cell: (info) => <span className="text-dim block max-w-xs truncate" title={info.getValue()}>{info.getValue()}</span>,
  }),
  columnHelper.accessor("source", {
    header: "Source",
    cell: (info) => <SourceBadge source={info.getValue()} />,
  }),
  columnHelper.accessor("discovery_date", {
    header: "Date",
    cell: (info) => <span className="text-dim font-mono tabular-nums whitespace-nowrap">{formatDate(info.getValue())}</span>,
  }),
  columnHelper.accessor("linkedin_url", {
    header: "LinkedIn",
    enableSorting: false,
    cell: (info) => (
      <a href={info.getValue()} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-accent hover:text-accent-strong font-medium whitespace-nowrap">
        Profile <ExternalLink size={12} />
      </a>
    ),
  }),
  columnHelper.display({
    id: "actions",
    header: "",
    enableSorting: false,
    cell: (info) => <FollowButton personId={info.row.original.id} size={15} />,
  }),
];

export default function CompanyDetail() {
  const { name } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [globalFilter, setGlobalFilter] = useState("");
  const { refreshKey } = useRun();

  useEffect(() => {
    let cancelled = false;
    setData(null);
    api
      .companyDetail(name)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [name, refreshKey]);

  const people = useMemo(() => data?.people ?? [], [data]);

  return (
    <PageShell
      title={name}
      subtitle="Company detail"
      right={
        <Link to="/companies" className="hidden sm:inline-flex items-center gap-1.5 text-[13px] text-dim hover:text-ink">
          <ArrowLeft size={14} /> All companies
        </Link>
      }
    >
      {error && (
        <div className="mb-4 rounded-md border border-danger/30 bg-danger-soft text-danger text-[13px] px-4 py-3">
          {error}
        </div>
      )}

      {error ? null : !data ? (
        <div className="flex items-center gap-2 justify-center text-dim py-12">
          <ScanLoader size={20} /> Loading…
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <Card className="p-5">
              <div className="text-[12px] font-medium text-dim uppercase tracking-[0.04em] mb-3">Title Breakdown</div>
              <ul className="flex flex-col gap-2">
                {data.title_breakdown.slice(0, 8).map((t) => (
                  <li key={t.title} className="flex items-center justify-between text-[13px]">
                    <span className="text-ink truncate pr-3">{t.title || "—"}</span>
                    <span className="font-mono tabular-nums text-dim shrink-0">{t.n}</span>
                  </li>
                ))}
              </ul>
            </Card>
            <Card className="p-5">
              <div className="text-[12px] font-medium text-dim uppercase tracking-[0.04em] mb-3">Source Breakdown</div>
              <ul className="flex flex-col gap-2">
                {data.source_breakdown.map((s) => (
                  <li key={s.source} className="flex items-center justify-between text-[13px]">
                    <SourceBadge source={s.source} />
                    <span className="font-mono tabular-nums text-dim">{s.n}</span>
                  </li>
                ))}
              </ul>
            </Card>
          </div>

          <DataTable
            columns={columns}
            data={people}
            globalFilter={globalFilter}
            onGlobalFilterChange={setGlobalFilter}
            searchPlaceholder="Search people at this company…"
            emptyIcon={Users}
            emptyTitle="No people found"
            pageSize={12}
            exportFilename={`helix_${name}.csv`}
          />
        </>
      )}
    </PageShell>
  );
}
