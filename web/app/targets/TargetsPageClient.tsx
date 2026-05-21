// app/targets/TargetsPageClient.tsx
"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { TargetItem } from "@/lib/types";
import Card from "@/components/ui/Card";
import StatusChip from "@/components/ui/StatusChip";
import { cn } from "@/lib/utils";

interface EditState {
  targetRatio: number;
  warning_thr: number;
  danger_thr: number;
}

/** 금액/비율 값 포맷 */
function fmtVal(val: number, unit?: string): string {
  if (unit === "원") {
    if (val >= 100_000_000) return `${(val / 100_000_000).toFixed(1)}억원`;
    if (val >= 10_000_000)  return `${(val / 10_000_000).toFixed(1)}천만원`;
    if (val >= 1_000_000)   return `${(val / 1_000_000).toFixed(1)}백만원`;
    return `${val.toLocaleString("ko-KR")}원`;
  }
  return `${val.toFixed(1)}%`;
}

export default function TargetsPageClient() {
  const [targets, setTargets] = useState<TargetItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [editMap, setEditMap] = useState<Record<string, EditState>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  useEffect(() => {
    fetchTargets();
  }, []);

  const fetchTargets = () => {
    setLoading(true);
    api
      .getTargets()
      .then((data) => {
        setTargets(data);
        const map: Record<string, EditState> = {};
        data.forEach((t) => {
          map[t.asset_class] = {
            targetRatio: t.targetRatio,
            warning_thr: 5,
            danger_thr: 10,
          };
        });
        setEditMap(map);
      })
      .catch(() => setTargets([]))
      .finally(() => setLoading(false));
  };

  const handleChange = (asset: string, field: keyof EditState, value: number) => {
    setEditMap((prev) => ({
      ...prev,
      [asset]: { ...prev[asset], [field]: value },
    }));
  };

  const handleSave = async (asset: string) => {
    setSaving(asset);
    try {
      const edit = editMap[asset];
      await api.updateTarget({
        asset_class: asset,
        target_value: edit.targetRatio,
        warning_thr: edit.warning_thr,
        danger_thr: edit.danger_thr,
      });
      setMsg({ type: "ok", text: `${asset} 목표가 저장되었습니다.` });
      await fetchTargets();
    } catch (e) {
      setMsg({ type: "err", text: "저장 실패: " + String(e) });
    } finally {
      setSaving(null);
      setTimeout(() => setMsg(null), 3000);
    }
  };

  // 자산배분 vs 기타 목표 분리
  const allocTargets = targets.filter((t) => (t.target_type ?? "asset_allocation") === "asset_allocation");
  const specialTargets = targets.filter((t) => t.target_type && t.target_type !== "asset_allocation");
  const totalTarget = allocTargets.reduce((s, t) => {
    const edit = editMap[t.asset_class];
    return s + (edit ? edit.targetRatio : t.targetRatio);
  }, 0);

  return (
    <div className="p-6 space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">목표 수치 관리</h1>
          <p className="text-sm text-slate-400">자산 배분 목표 비중 및 경고 임계값 설정</p>
        </div>
        <div className={cn(
          "text-sm font-semibold px-3 py-1 rounded-full",
          Math.abs(totalTarget - 100) < 0.5 ? "bg-green-500/20 text-green-400" : "bg-yellow-500/20 text-yellow-400"
        )}>
          자산배분 합계: {totalTarget.toFixed(1)}%
          {Math.abs(totalTarget - 100) >= 0.5 && " ⚠ (100%가 아님)"}
        </div>
      </div>

      {msg && (
        <div className={cn(
          "px-4 py-2 rounded-lg text-sm font-medium",
          msg.type === "ok" ? "bg-green-500/20 text-green-300" : "bg-red-500/20 text-red-300"
        )}>
          {msg.text}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-40 text-slate-500">로딩 중...</div>
      ) : (
        <>
          {/* ── 자산 배분 목표 ── */}
          <div>
            <h2 className="text-base font-semibold text-slate-300 mb-3">자산 배분 목표</h2>

            {/* 요약 차트 */}
            <Card title="현재 vs 목표 비중 비교">
              <div className="space-y-3">
                {allocTargets.map((t) => {
                  const edit = editMap[t.asset_class] ?? { targetRatio: t.targetRatio };
                  return (
                    <div key={t.asset_class}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm text-white font-medium">{t.asset_class}</span>
                        <div className="flex items-center gap-3 text-xs">
                          <span className="text-slate-400">현재 <span className="text-white font-semibold">{t.currentRatio.toFixed(1)}%</span></span>
                          <span className="text-slate-400">목표 <span className="text-blue-400 font-semibold">{edit.targetRatio.toFixed(1)}%</span></span>
                          <StatusChip status={t.level} />
                        </div>
                      </div>
                      <div className="relative h-5 bg-slate-700 rounded-full overflow-hidden">
                        <div className="absolute top-0 bottom-0 w-0.5 bg-blue-400 z-10"
                          style={{ left: `${Math.min(edit.targetRatio, 100)}%` }} />
                        <div className={cn(
                          "h-full rounded-full transition-all",
                          t.level === "danger" ? "bg-red-500/70" :
                          t.level === "warning" ? "bg-yellow-500/70" : "bg-green-500/50"
                        )} style={{ width: `${Math.min(t.currentRatio, 100)}%` }} />
                      </div>
                      <div className="text-[10px] text-slate-600 mt-0.5">
                        괴리 {t.deviation > 0 ? "+" : ""}{t.deviation.toFixed(1)}%
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>

            {/* 개별 편집 카드 */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
              {allocTargets.map((t) => {
                const edit = editMap[t.asset_class] ?? { targetRatio: 0, warning_thr: 5, danger_thr: 10 };
                return (
                  <Card key={t.asset_class} title={t.asset_class} extra={<StatusChip status={t.level} />}>
                    <div className="space-y-4">
                      <div>
                        <div className="flex justify-between text-xs text-slate-400 mb-1">
                          <span>현재 비중</span>
                          <span className="text-white font-bold">{t.currentRatio.toFixed(1)}%</span>
                        </div>
                      </div>
                      <div>
                        <label className="text-xs text-slate-400 block mb-1">
                          목표 비중: <span className="text-blue-400 font-bold">{edit.targetRatio.toFixed(1)}%</span>
                        </label>
                        <input type="range" min={0} max={100} step={0.5}
                          value={edit.targetRatio}
                          onChange={(e) => handleChange(t.asset_class, "targetRatio", parseFloat(e.target.value))}
                          className="w-full accent-blue-500" />
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="text-[10px] text-slate-500 block mb-1">경고 임계값 (%)</label>
                          <input type="number" min={1} max={50} step={0.5}
                            value={edit.warning_thr}
                            onChange={(e) => handleChange(t.asset_class, "warning_thr", parseFloat(e.target.value))}
                            className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1
                                       text-sm text-white focus:outline-none focus:border-yellow-500" />
                        </div>
                        <div>
                          <label className="text-[10px] text-slate-500 block mb-1">위험 임계값 (%)</label>
                          <input type="number" min={1} max={50} step={0.5}
                            value={edit.danger_thr}
                            onChange={(e) => handleChange(t.asset_class, "danger_thr", parseFloat(e.target.value))}
                            className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1
                                       text-sm text-white focus:outline-none focus:border-red-500" />
                        </div>
                      </div>
                      <button
                        onClick={() => handleSave(t.asset_class)}
                        disabled={saving === t.asset_class}
                        className="w-full py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50
                                   text-white text-sm font-medium rounded-lg transition-colors"
                      >
                        {saving === t.asset_class ? "저장 중..." : "저장"}
                      </button>
                    </div>
                  </Card>
                );
              })}
            </div>
          </div>

          {/* ── 투자/수익 목표 ── */}
          {specialTargets.length > 0 && (
            <div>
              <h2 className="text-base font-semibold text-slate-300 mb-3">투자 · 수익 목표</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {specialTargets.map((t) => {
                  const unit = t.unit ?? "%";
                  const edit = editMap[t.asset_class] ?? { targetRatio: t.targetRatio, warning_thr: 5, danger_thr: 10 };
                  const isAmount = unit === "원";
                  const step = isAmount ? 500_000 : 0.5;
                  const maxVal = isAmount ? t.targetRatio * 3 : 100;

                  return (
                    <Card key={t.asset_class} title={t.asset_class} extra={<StatusChip status={t.level} />}>
                      <div className="space-y-4">
                        {/* 현재/목표 표시 */}
                        <div className="flex justify-between text-sm">
                          <div>
                            <p className="text-[10px] text-slate-500 mb-1">현재</p>
                            <p className="text-white font-bold">{fmtVal(t.currentRatio, unit)}</p>
                          </div>
                          <div className="text-right">
                            <p className="text-[10px] text-slate-500 mb-1">목표</p>
                            <p className="text-blue-400 font-bold">{fmtVal(edit.targetRatio, unit)}</p>
                          </div>
                          <div className="text-right">
                            <p className="text-[10px] text-slate-500 mb-1">달성률</p>
                            <p className={cn(
                              "font-bold",
                              t.level === "danger" ? "text-red-400" :
                              t.level === "warning" ? "text-yellow-400" : "text-green-400"
                            )}>
                              {edit.targetRatio > 0
                                ? `${((t.currentRatio / edit.targetRatio) * 100).toFixed(0)}%`
                                : "—"}
                            </p>
                          </div>
                        </div>

                        {/* 진행 바 */}
                        <div className="relative h-3 bg-slate-700 rounded-full overflow-hidden">
                          <div className={cn(
                            "h-full rounded-full transition-all",
                            t.level === "danger" ? "bg-red-500/70" :
                            t.level === "warning" ? "bg-yellow-500/70" : "bg-green-500/60"
                          )} style={{ width: `${Math.min((t.currentRatio / (edit.targetRatio || 1)) * 100, 100)}%` }} />
                        </div>

                        {/* 목표값 편집 */}
                        <div>
                          <label className="text-xs text-slate-400 block mb-1">
                            목표 {isAmount ? "금액" : "비율"}: <span className="text-blue-400 font-bold">{fmtVal(edit.targetRatio, unit)}</span>
                          </label>
                          <input type="range"
                            min={isAmount ? 1_000_000 : 0.5}
                            max={maxVal}
                            step={step}
                            value={edit.targetRatio}
                            onChange={(e) => handleChange(t.asset_class, "targetRatio", parseFloat(e.target.value))}
                            className="w-full accent-blue-500" />
                        </div>

                        {/* 임계값 편집 */}
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <label className="text-[10px] text-slate-500 block mb-1">
                              경고 임계값 {isAmount ? "(%)" : "(%)"}
                            </label>
                            <input type="number" min={1} max={50} step={0.5}
                              value={edit.warning_thr}
                              onChange={(e) => handleChange(t.asset_class, "warning_thr", parseFloat(e.target.value))}
                              className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1
                                         text-sm text-white focus:outline-none focus:border-yellow-500" />
                          </div>
                          <div>
                            <label className="text-[10px] text-slate-500 block mb-1">위험 임계값 (%)</label>
                            <input type="number" min={1} max={50} step={0.5}
                              value={edit.danger_thr}
                              onChange={(e) => handleChange(t.asset_class, "danger_thr", parseFloat(e.target.value))}
                              className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1
                                         text-sm text-white focus:outline-none focus:border-red-500" />
                          </div>
                        </div>

                        <button
                          onClick={() => handleSave(t.asset_class)}
                          disabled={saving === t.asset_class}
                          className="w-full py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50
                                     text-white text-sm font-medium rounded-lg transition-colors"
                        >
                          {saving === t.asset_class ? "저장 중..." : "저장"}
                        </button>
                      </div>
                    </Card>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

