import * as RadixTooltip from "@radix-ui/react-tooltip";

export function TooltipProvider({ children }) {
  return <RadixTooltip.Provider delayDuration={300}>{children}</RadixTooltip.Provider>;
}

export default function Tooltip({ content, children }) {
  return (
    <RadixTooltip.Root>
      <RadixTooltip.Trigger asChild>{children}</RadixTooltip.Trigger>
      <RadixTooltip.Portal>
        <RadixTooltip.Content
          sideOffset={6}
          className="z-50 rounded-md bg-surface-3 border border-border px-2.5 py-1.5 text-[11.5px] text-ink shadow-lg max-w-xs"
        >
          {content}
          <RadixTooltip.Arrow className="fill-surface-3" />
        </RadixTooltip.Content>
      </RadixTooltip.Portal>
    </RadixTooltip.Root>
  );
}
