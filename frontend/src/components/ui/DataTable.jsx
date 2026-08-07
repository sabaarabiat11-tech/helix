import { useState } from "react";
import {
  useReactTable, getCoreRowModel, getSortedRowModel, getFilteredRowModel,
  getPaginationRowModel, flexRender,
} from "@tanstack/react-table";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { ArrowUpDown, ChevronLeft, ChevronRight, Columns3, Copy, Download, Check } from "lucide-react";
import { cn } from "../../lib/cn";
import Button from "./Button";
import SearchInput from "../SearchInput";
import { SkeletonRow } from "./Skeleton";
import EmptyState from "./EmptyState";

/** Reusable premium data table: search, sort, client-side pagination, column
 * visibility, copy-as-TSV, CSV export — every table in the app should use
 * this instead of hand-rolling markup, so behavior stays consistent. */
export default function DataTable({
  columns,
  data,
  loading,
  emptyIcon,
  emptyTitle = "Nothing here yet",
  emptyDescription,
  globalFilter,
  onGlobalFilterChange,
  searchPlaceholder = "Search…",
  pageSize = 12,
  exportFilename = "export.csv",
  toolbarExtra,
}) {
  const [sorting, setSorting] = useState([]);
  const [columnVisibility, setColumnVisibility] = useState({});
  const [pagination, setPagination] = useState({ pageIndex: 0, pageSize });
  const [copied, setCopied] = useState(false);

  const table = useReactTable({
    data,
    columns,
    state: { sorting, columnVisibility, globalFilter, pagination },
    onSortingChange: setSorting,
    onColumnVisibilityChange: setColumnVisibility,
    onGlobalFilterChange,
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  function copyVisibleAsTsv() {
    const visibleCols = table.getVisibleLeafColumns().filter((c) => c.id !== "actions");
    const header = visibleCols.map((c) => c.columnDef.header).join("\t");
    const rows = table.getFilteredRowModel().rows.map((r) =>
      visibleCols.map((c) => String(r.getValue(c.id) ?? "")).join("\t")
    );
    navigator.clipboard.writeText([header, ...rows].join("\n"));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  function exportCsv() {
    const visibleCols = table.getVisibleLeafColumns().filter((c) => c.id !== "actions");
    const escape = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const header = visibleCols.map((c) => escape(c.columnDef.header)).join(",");
    const rows = table.getFilteredRowModel().rows.map((r) =>
      visibleCols.map((c) => escape(r.getValue(c.id))).join(",")
    );
    const blob = new Blob([[header, ...rows].join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = exportFilename;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center gap-3 mb-4">
        {onGlobalFilterChange && (
          <SearchInput value={globalFilter ?? ""} onChange={onGlobalFilterChange} placeholder={searchPlaceholder} className="sm:max-w-sm" />
        )}
        {toolbarExtra}
        <div className="flex items-center gap-2 sm:ml-auto">
          <DropdownMenu.Root>
            <DropdownMenu.Trigger asChild>
              <Button variant="outline" size="sm"><Columns3 size={13} /> Columns</Button>
            </DropdownMenu.Trigger>
            <DropdownMenu.Portal>
              <DropdownMenu.Content
                align="end"
                className="z-50 min-w-[180px] rounded-md border border-border bg-surface shadow-xl p-1"
                style={{ animation: "helix-pop 120ms ease-out" }}
              >
                {table.getAllLeafColumns().filter((c) => c.id !== "actions").map((col) => (
                  <DropdownMenu.CheckboxItem
                    key={col.id}
                    checked={col.getIsVisible()}
                    onCheckedChange={col.getToggleVisibilityHandler()}
                    className="flex items-center gap-2 px-2.5 py-1.5 text-[12.5px] text-ink rounded-sm cursor-pointer data-[highlighted]:bg-surface-2 outline-none"
                  >
                    <span className="w-3.5 h-3.5 rounded-sm border border-border flex items-center justify-center">
                      {col.getIsVisible() && <Check size={11} className="text-accent" />}
                    </span>
                    {typeof col.columnDef.header === "string" ? col.columnDef.header : col.id}
                  </DropdownMenu.CheckboxItem>
                ))}
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
          <Button variant="outline" size="sm" onClick={copyVisibleAsTsv}>
            {copied ? <Check size={13} className="text-success" /> : <Copy size={13} />} {copied ? "Copied" : "Copy"}
          </Button>
          <Button variant="outline" size="sm" onClick={exportCsv}>
            <Download size={13} /> Export
          </Button>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-surface overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id} className="border-b border-border bg-surface-2/60">
                  {hg.headers.map((header) => (
                    <th key={header.id} className="text-left px-4 py-2.5 font-medium text-dim whitespace-nowrap">
                      {header.isPlaceholder ? null : (
                        <button
                          onClick={header.column.getToggleSortingHandler()}
                          disabled={!header.column.getCanSort()}
                          className={cn("inline-flex items-center gap-1", header.column.getCanSort() && "hover:text-ink")}
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                          {header.column.getCanSort() && (
                            <ArrowUpDown size={12} className={header.column.getIsSorted() ? "text-accent" : "text-faint"} />
                          )}
                        </button>
                      )}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 6 }).map((_, i) => <SkeletonRow key={i} columns={columns.length} />)
              ) : table.getRowModel().rows.length === 0 ? (
                <tr>
                  <td colSpan={columns.length}>
                    <EmptyState icon={emptyIcon} title={emptyTitle} description={emptyDescription} />
                  </td>
                </tr>
              ) : (
                table.getRowModel().rows.map((row) => (
                  <tr key={row.id} className="border-b border-border last:border-0 hover:bg-surface-2/40">
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="px-4 py-2.5 align-middle">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {!loading && table.getPageCount() > 0 && (
        <div className="flex items-center justify-between px-1 py-3 text-[12.5px] text-dim">
          <span>
            {table.getFilteredRowModel().rows.length === 0
              ? "0"
              : `${pagination.pageIndex * pagination.pageSize + 1}–${Math.min(
                  (pagination.pageIndex + 1) * pagination.pageSize,
                  table.getFilteredRowModel().rows.length
                )}`}{" "}
            of <span className="font-mono tabular-nums">{table.getFilteredRowModel().rows.length}</span>
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
              className="p-1.5 rounded-md hover:bg-surface-2 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronLeft size={16} />
            </button>
            <span className="px-2 font-mono tabular-nums">
              {pagination.pageIndex + 1} / {Math.max(1, table.getPageCount())}
            </span>
            <button
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
              className="p-1.5 rounded-md hover:bg-surface-2 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
