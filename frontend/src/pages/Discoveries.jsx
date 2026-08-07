import { useEffect, useMemo, useState } from "react";
import { ExternalLink, Users } from "lucide-react";
import { createColumnHelper } from "@tanstack/react-table";
import { api } from "../api/client";
import { useRun } from "../hooks/RunContext";
import PageShell from "../components/PageShell";
import DataTable from "../components/ui/DataTable";
import SourceBadge from "../components/SourceBadge";
import FollowButton from "../components/FollowButton";
import { formatDate } from "../lib/format";

const columnHelper = createColumnHelper();

const columns = [
  columnHelper.accessor("name", {
    header: "Name",
    cell: (info) => <span className="font-medium text-ink whitespace-nowrap">{info.getValue()}</span>,
  }),
  columnHelper.accessor("company", {
    header: "Company",
    cell: (info) => <span className="text-dim whitespace-nowrap">{info.getValue()}</span>,
  }),
  columnHelper.accessor("title", {
    header: "Title",
    cell: (info) => (
      <span className="text-dim block max-w-xs truncate" title={info.getValue()}>{info.getValue()}</span>
    ),
  }),
  columnHelper.accessor("source", {
    header: "Source",
    cell: (info) => <SourceBadge source={info.getValue()} />,
  }),
  columnHelper.accessor("discovery_date", {
    header: "Date Discovered",
    cell: (info) => <span className="text-dim font-mono tabular-nums whitespace-nowrap">{formatDate(info.getValue())}</span>,
  }),
  columnHelper.accessor("linkedin_url", {
    header: "LinkedIn",
    enableSorting: false,
    cell: (info) => (
      <a
        href={info.getValue()}
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-1 text-accent hover:text-accent-strong font-medium whitespace-nowrap"
      >
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

export default function Discoveries() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [globalFilter, setGlobalFilter] = useState("");
  const { refreshKey } = useRun();

  useEffect(() => {
    let cancelled = false;
    api
      .discoveries({ page_size: 5000 })
      .then((d) => !cancelled && setRows(d.results))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  const data = useMemo(() => rows ?? [], [rows]);

  return (
    <PageShell title="New Discoveries" subtitle="Every person the pipeline has found, browsable and searchable">
      {error && (
        <div className="mb-4 rounded-md border border-danger/30 bg-danger-soft text-danger text-[13px] px-4 py-3">
          {error}
        </div>
      )}
      <DataTable
        columns={columns}
        data={data}
        loading={!rows}
        globalFilter={globalFilter}
        onGlobalFilterChange={setGlobalFilter}
        searchPlaceholder="Search by name, company, or title…"
        emptyIcon={Users}
        emptyTitle="No people match these filters"
        emptyDescription="Try a different search term, or run the pipeline to discover more people."
        pageSize={15}
        exportFilename="helix_discoveries.csv"
      />
    </PageShell>
  );
}
