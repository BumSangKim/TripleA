// components/dashboard/MemoPanel.tsx
"use client";
import { useState, useEffect } from "react";
import Card from "@/components/ui/Card";

export default function MemoPanel() {
  const [memo, setMemo] = useState("");
  const [saved, setSaved] = useState(true);
  const [saving, setSaving] = useState(false);

  // 마운트 시 localStorage에서 이전 메모 복원
  useEffect(() => {
    const timer = window.setTimeout(() => {
      try {
        const raw = localStorage.getItem("triplea_daily_memo");
        if (raw) {
          const parsed = JSON.parse(raw);
          const text = typeof parsed === "string" ? parsed : parsed?.text;
          if (text) setMemo(text);
        }
      } catch {
        // localStorage 접근 실패는 메모 기본값 유지로 처리한다.
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const handleChange = (v: string) => {
    setMemo(v);
    setSaved(false);
  };

  const handleSave = async () => {
    setSaving(true);
    // 로컬 스토리지 저장 (API 없을 때 fallback)
    try {
      localStorage.setItem("triplea_daily_memo", JSON.stringify({ text: memo, saved_at: new Date().toISOString() }));
    } catch {}
    await new Promise((r) => setTimeout(r, 300));
    setSaved(true);
    setSaving(false);
  };

  return (
    <Card title="운영 메모" extra={
      saved
        ? <span className="text-[10px] text-green-400">✓ 저장됨</span>
        : <span className="text-[10px] text-yellow-400">• 미저장</span>
    }>
      <textarea
        value={memo}
        onChange={(e) => handleChange(e.target.value)}
        rows={4}
        placeholder="오늘의 운영 메모를 작성하세요..."
        className="w-full bg-slate-700/50 border border-slate-600 rounded-lg p-3 text-sm text-slate-300
                   placeholder:text-slate-600 resize-none focus:outline-none focus:border-blue-500
                   transition-colors"
      />
      <div className="flex items-center justify-between mt-2">
        <span className="text-[10px] text-slate-600">{memo.length} 자</span>
        <button
          onClick={handleSave}
          disabled={saving || saved}
          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white
                     text-xs font-medium rounded-md transition-colors"
        >
          {saving ? "저장 중..." : "메모 작성"}
        </button>
      </div>
    </Card>
  );
}
