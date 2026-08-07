import { useState } from "react";
import { motion } from "framer-motion";
import { ExternalLink, Star, Pencil } from "lucide-react";
import { useWatchlist } from "../hooks/WatchlistContext";
import PageShell from "../components/PageShell";
import Card from "../components/ui/Card";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Input from "../components/ui/Input";
import EmptyState from "../components/ui/EmptyState";
import { Dialog, DialogContent } from "../components/ui/Dialog";
import { formatDate } from "../lib/format";

const PRIORITY_TONE = { high: "danger", medium: "warning", low: "neutral" };
const STATUS_TONE = { new: "accent", contacted: "warning", responded: "success", archived: "neutral" };

function EditDialog({ entry, onClose, onSave }) {
  const [notes, setNotes] = useState(entry.notes);
  const [tags, setTags] = useState(entry.tags);
  const [priority, setPriority] = useState(entry.priority);
  const [status, setStatus] = useState(entry.status);
  const [reminderDate, setReminderDate] = useState(entry.reminder_date);

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent title={entry.name}>
        <div className="flex flex-col gap-4">
          <div>
            <label className="text-[11.5px] font-medium text-dim mb-1.5 block">Notes</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-[13px] text-ink focus:border-accent focus:outline-none resize-none"
            />
          </div>
          <div>
            <label className="text-[11.5px] font-medium text-dim mb-1.5 block">Tags (comma-separated)</label>
            <Input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="conference, follow-up" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11.5px] font-medium text-dim mb-1.5 block">Priority</label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                className="w-full rounded-md border border-border bg-surface px-3 py-2 text-[13px] text-ink focus:border-accent focus:outline-none"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </div>
            <div>
              <label className="text-[11.5px] font-medium text-dim mb-1.5 block">Status</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full rounded-md border border-border bg-surface px-3 py-2 text-[13px] text-ink focus:border-accent focus:outline-none"
              >
                <option value="new">New</option>
                <option value="contacted">Contacted</option>
                <option value="responded">Responded</option>
                <option value="archived">Archived</option>
              </select>
            </div>
          </div>
          <div>
            <label className="text-[11.5px] font-medium text-dim mb-1.5 block">Reminder date</label>
            <Input type="date" value={reminderDate} onChange={(e) => setReminderDate(e.target.value)} />
          </div>
          <div className="flex justify-end gap-2 mt-1">
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button
              variant="primary"
              onClick={() => onSave({ notes, tags, priority, status, reminder_date: reminderDate })}
            >
              Save
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function Watchlist() {
  const { entries, loading, unfollow, updateEntry } = useWatchlist();
  const [editing, setEditing] = useState(null);

  return (
    <PageShell title="Watchlist" subtitle="People you're following, with notes, tags, priority, and reminders">
      {loading ? null : entries.length === 0 ? (
        <EmptyState
          icon={Star}
          title="Your watchlist is empty"
          description="Star anyone from New Discoveries, Recommendations, or Companies to add them here."
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {entries.map((e, i) => (
            <motion.div
              key={e.watchlist_id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: i * 0.03 }}
            >
              <Card hover className="p-5 flex flex-col gap-3 h-full">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <h3 className="font-display font-semibold text-[14px] text-ink truncate">{e.name}</h3>
                    <p className="text-[12px] text-dim truncate">{e.title} · {e.company}</p>
                  </div>
                  <button onClick={() => unfollow(e.person_id)} className="text-accent shrink-0" title="Unfollow">
                    <Star size={16} className="fill-accent" />
                  </button>
                </div>

                <div className="flex flex-wrap gap-1.5">
                  <Badge tone={PRIORITY_TONE[e.priority]} size="sm">{e.priority}</Badge>
                  <Badge tone={STATUS_TONE[e.status]} size="sm" dot={false}>{e.status}</Badge>
                  {e.tags && e.tags.split(",").filter(Boolean).map((t) => (
                    <Badge key={t} tone="neutral" size="sm" dot={false}>{t.trim()}</Badge>
                  ))}
                </div>

                {e.notes && <p className="text-[12.5px] text-dim line-clamp-2">{e.notes}</p>}

                <div className="text-[11px] text-faint font-mono">
                  Followed {formatDate(e.followed_at?.slice(0, 10))}
                  {e.reminder_date && <> · Reminder {formatDate(e.reminder_date)}</>}
                </div>

                <div className="mt-auto flex items-center justify-between pt-2">
                  <a
                    href={e.linkedin_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-[12px] text-accent hover:text-accent-strong font-medium"
                  >
                    LinkedIn <ExternalLink size={11} />
                  </a>
                  <Button variant="ghost" size="sm" onClick={() => setEditing(e)}>
                    <Pencil size={13} /> Edit
                  </Button>
                </div>
              </Card>
            </motion.div>
          ))}
        </div>
      )}

      {editing && (
        <EditDialog
          entry={editing}
          onClose={() => setEditing(null)}
          onSave={async (fields) => {
            await updateEntry(editing.person_id, fields);
            setEditing(null);
          }}
        />
      )}
    </PageShell>
  );
}
