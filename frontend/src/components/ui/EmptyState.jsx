import Reveal from "./Reveal";

export default function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <Reveal
      y={8}
      duration={0.3}
      className="flex flex-col items-center justify-center text-center py-16 px-6"
    >
      {Icon && (
        <div className="w-14 h-14 rounded-2xl bg-accent-soft text-accent flex items-center justify-center mb-4">
          <Icon size={24} strokeWidth={1.75} />
        </div>
      )}
      <h3 className="font-display font-semibold text-[15px] text-ink mb-1">{title}</h3>
      {description && <p className="text-[13px] text-faint max-w-sm mb-4">{description}</p>}
      {action}
    </Reveal>
  );
}
