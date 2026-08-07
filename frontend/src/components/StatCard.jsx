import { motion } from "framer-motion";
import Card from "./ui/Card";
import AnimatedCounter from "./ui/AnimatedCounter";

export default function StatCard({ label, value, sub, icon: Icon, tone = "default", delay = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay }}
    >
      <Card hover className="p-5 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-[12px] font-medium text-dim uppercase tracking-[0.04em]">{label}</span>
          {Icon && (
            <span
              className={`inline-flex items-center justify-center w-8 h-8 rounded-md ${
                tone === "accent" ? "bg-accent-soft text-accent" : "bg-surface-2 text-faint"
              }`}
            >
              <Icon size={16} strokeWidth={2} />
            </span>
          )}
        </div>
        {typeof value === "number" ? (
          <AnimatedCounter value={value} className="font-mono font-medium text-[32px] leading-none text-ink tabular-nums" />
        ) : (
          <div className="font-mono font-medium text-[32px] leading-none text-ink tabular-nums">{value}</div>
        )}
        {sub && <div className="text-[12.5px] text-faint">{sub}</div>}
      </Card>
    </motion.div>
  );
}
