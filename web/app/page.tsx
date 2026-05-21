// app/page.tsx  –  대시보드 메인 페이지 (Server Component + 클라이언트 하이브리드)
import { Suspense } from "react";
import DashboardClient from "@/components/dashboard/DashboardClient";

export const revalidate = 60; // 60초마다 ISR 갱신

async function fetchDashboard() {
  const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  try {
    const res = await fetch(`${base}/api/dashboard/summary`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export default async function DashboardPage() {
  const data = await fetchDashboard();
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">대시보드</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            {new Date().toLocaleDateString("ko-KR", { year: "numeric", month: "long", day: "numeric", weekday: "long" })}
          </p>
        </div>
      </div>
      <Suspense fallback={<LoadingSkeleton />}>
        <DashboardClient initialData={data} />
      </Suspense>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="grid grid-cols-5 gap-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-24 bg-slate-800 rounded-xl" />
        ))}
      </div>
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 h-48 bg-slate-800 rounded-xl" />
        <div className="h-48 bg-slate-800 rounded-xl" />
      </div>
    </div>
  );
}
