import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type PromptCardProps = {
  icon: LucideIcon;
  title: string;
  question: string;
  onClick: () => void;
  disabled?: boolean;
};

export function PromptCard({ icon: Icon, title, question, onClick, disabled }: PromptCardProps) {
  return (
    <button
      type="button"
      className={cn(
        "prompt-card text-left rounded-xl border border-slate-200 bg-white shadow-sm",
        "hover:shadow-md hover:border-emerald-300 p-4 cursor-pointer transition-all group",
        "disabled:opacity-50 disabled:cursor-not-allowed",
      )}
      onClick={onClick}
      disabled={disabled}
    >
      <div className="flex items-center gap-2 mb-2">
        <span className="flex items-center justify-center w-8 h-8 rounded-lg bg-emerald-50 text-emerald-700 group-hover:bg-emerald-100 transition-colors">
          <Icon size={16} aria-hidden="true" />
        </span>
        <span className="font-semibold text-sm text-slate-800">{title}</span>
      </div>
      <p className="text-xs text-slate-500 leading-relaxed m-0">{question}</p>
    </button>
  );
}
