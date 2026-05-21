// components/ui/Card.tsx
import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface CardProps {
  children: ReactNode;
  className?: string;
  title?: string;
  extra?: ReactNode;
}

export default function Card({ children, className, title, extra }: CardProps) {
  return (
    <div className={cn("bg-slate-800 rounded-xl border border-slate-700 p-4", className)}>
      {(title || extra) && (
        <div className="flex items-center justify-between mb-3">
          {title && <h3 className="text-sm font-semibold text-slate-300">{title}</h3>}
          {extra && <div className="text-xs text-slate-500">{extra}</div>}
        </div>
      )}
      {children}
    </div>
  );
}
