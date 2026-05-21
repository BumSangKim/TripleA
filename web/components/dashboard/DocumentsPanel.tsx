// components/dashboard/DocumentsPanel.tsx
"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import Card from "@/components/ui/Card";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const DOC_TYPES = [
  { key: "report",   icon: "📋", label: "리포트" },
  { key: "idea",     icon: "💡", label: "투자 아이디어" },
  { key: "news",     icon: "📰", label: "뉴스 요약" },
  { key: "memo",     icon: "📝", label: "회의 메모" },
  { key: "backtest", icon: "🔍", label: "백테스트" },
  { key: "other",    icon: "🗂️", label: "기타 자료" },
];

export default function DocumentsPanel() {
  const [counts, setCounts] = useState<Record<string, number>>({});

  useEffect(() => {
    fetch(`${BASE_URL}/api/documents/counts`)
      .then((r) => r.json())
      .then((d) => setCounts(d))
      .catch(() => {});
  }, []);

  return (
    <Card title="각종 자료" extra={<Link href="/documents" className="text-blue-400 hover:underline text-xs">더보기 &gt;</Link>}>
      <div className="grid grid-cols-3 gap-2">
        {DOC_TYPES.map((d) => (
          <Link
            key={d.key}
            href="/documents"
            className="flex flex-col items-center justify-center p-3 bg-slate-700/50 rounded-lg hover:bg-slate-700 transition-colors cursor-pointer"
          >
            <span className="text-2xl mb-1">{d.icon}</span>
            <span className="text-xs text-slate-400">{d.label}</span>
            <span className="text-sm text-white font-medium">{counts[d.key] ?? 0}</span>
          </Link>
        ))}
      </div>
    </Card>
  );
}
