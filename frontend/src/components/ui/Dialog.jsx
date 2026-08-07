import * as RadixDialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "../../lib/cn";

export function Dialog({ open, onOpenChange, children }) {
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      {children}
    </RadixDialog.Root>
  );
}

export function DialogContent({ className, children, title }) {
  return (
    <RadixDialog.Portal>
      <RadixDialog.Overlay
        className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm"
        style={{ animation: "helix-fade 150ms ease-out" }}
      />
      <RadixDialog.Content
        className={cn(
          "fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 w-[calc(100%-2rem)] max-w-lg",
          "rounded-lg border border-border bg-surface shadow-2xl focus:outline-none",
          className
        )}
        style={{ animation: "helix-pop 150ms ease-out" }}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <RadixDialog.Title className="font-display font-semibold text-[14px] text-ink">
            {title}
          </RadixDialog.Title>
          <RadixDialog.Close className="p-1 rounded-md text-faint hover:text-ink hover:bg-surface-2">
            <X size={16} />
          </RadixDialog.Close>
        </div>
        <div className="p-5">{children}</div>
      </RadixDialog.Content>
    </RadixDialog.Portal>
  );
}
