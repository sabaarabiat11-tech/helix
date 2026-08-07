import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Building2, ChevronRight } from "lucide-react";
import { createColumnHelper } from "@tanstack/react-table";
import { api } from "../api/client";
import { useRun } from "../hooks/RunContext";
import PageShell from "../components/PageShell";
import DataTable from "../components/ui/DataTable";
import { formatDate } from "../lib/format";

const columnHelper = createColumnHelper();

function makeColumns(maxCount) {
  return [
    columnHelper.accessor("company", {
      header: "Company",
      cell: (info) => (
        <Link to={`/companies/${encodeURIComponent(info.getValue())}`} className="font-medium text-ink hover:text-accent whitespace-nowrap">
          {info.getValue()}
        </Link>
      ),
    }),
    columnHelper.accessor("n", {
      header: "People Found",
      cell: (info) => (
        <div className="flex items-center gap-2">
          <span className="font-mono tabular-nums text-ink w-8">{info.getValue()}</span>
          <div className="flex-1 h-1.5 rounded-full bg-surface-3 overflow-hidden max-w-[140px]">
            <div className="h-full bg-accent rounded-full" style={{ width: `${Math.max(6, (info.getValue() / maxCount) * 100)}%` }} />
          </div>
        </div>
      ),
    }),
    columnHelper.accessor("latest_date", {
      header: "Latest Discovery",
      cell: (info) => <span className="text-dim font-mono tabular-nums whitespace-nowrap">{formatDate(info.getValue())}</span>,
    }),
    columnHelper.display({
      id: "actions",
      header: "",
      enableSorting: false,
      cell: (info) => (
        <Link to={`/companies/${encodeURIComponent(info.row.original.company)}`} className="text-faint hover:text-accent">
          <ChevronRight size={16} />
        </Link>
      ),
    }),
  ];
}

export default function Companies() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [globalFilter, setGlobalFilter] = useState("");
  const { refreshKey } = useRun();

  useEffect(() => {
    let cancelled = false;
    api
      .companies()
      .then((d) => !cancelled && setRows(d))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  const data = useMemo(() => rows ?? [], [rows]);
  const maxCount = data.length ? Math.max(...data.map((c) => c.n)) : 1;
  const columns = useMemo(() => makeColumns(maxCount), [maxCount]);

  return (
    <PageShell title="Companies" subtitle="People discovered, grouped by company">
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
        searchPlaceholder="Search companies…"
        emptyIcon={Building2}
        emptyTitle="No companies match this search"
        pageSize={12}
        exportFilename="helix_companies.csv"
      />
    </PageShell>
  );
}
