// app/documents/DocumentsPageClient.tsx
"use client";
import { useCallback, useEffect, useState } from "react";
import type { DocumentItem } from "@/lib/types";
import Card from "@/components/ui/Card";
import { cn } from "@/lib/utils";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const DOC_TYPES = [
  { value: "all",      label: "전체",         icon: "📋" },
  { value: "report",   label: "리포트",       icon: "📊" },
  { value: "idea",     label: "투자 아이디어", icon: "💡" },
  { value: "memo",     label: "회의/운영 메모",icon: "📝" },
  { value: "news",     label: "뉴스 요약",    icon: "📰" },
  { value: "backtest", label: "백테스트",      icon: "⚙️" },
];

type FormState = { type: string; title: string; content: string; tags: string; url: string };
const EMPTY_FORM: FormState = { type: "memo", title: "", content: "", tags: "", url: "" };

interface DocumentsPageClientProps {
  defaultType?: string;
  pageTitle?: string;
}

export default function DocumentsPageClient({
  defaultType = "all",
  pageTitle,
}: DocumentsPageClientProps) {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState(defaultType);
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const fetchDocs = useCallback(() => {
    setLoading(true);
    fetch(`${BASE_URL}/api/documents?limit=200`)
      .then((r) => r.json())
      .then(setDocs)
      .catch(() => setDocs([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(fetchDocs, 0);
    return () => window.clearTimeout(timer);
  }, [fetchDocs]);

  const showMsg = (type: "ok" | "err", text: string) => {
    setMsg({ type, text });
    setTimeout(() => setMsg(null), 3000);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title.trim()) { showMsg("err", "제목을 입력하세요."); return; }
    setSaving(true);
    try {
      if (editingId !== null) {
        const res = await fetch(`${BASE_URL}/api/documents/${editingId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(form),
        });
        if (!res.ok) throw new Error("수정 실패");
        showMsg("ok", "수정되었습니다.");
      } else {
        const res = await fetch(`${BASE_URL}/api/documents`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(form),
        });
        if (!res.ok) throw new Error("저장 실패");
        showMsg("ok", "자료가 저장되었습니다.");
      }
      setShowForm(false);
      setForm(EMPTY_FORM);
      setEditingId(null);
      fetchDocs();
    } catch (err) {
      showMsg("err", String(err));
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (doc: DocumentItem) => {
    setForm({
      type: doc.type ?? "memo",
      title: doc.title,
      content: doc.content ?? "",
      tags: doc.tags ?? "",
      url: doc.url ?? "",
    });
    setEditingId(doc.id ?? null);
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleDelete = async (id: number) => {
    if (!confirm("이 자료를 삭제하시겠습니까?")) return;
    setDeletingId(id);
    try {
      const res = await fetch(`${BASE_URL}/api/documents/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("삭제 실패");
      showMsg("ok", "삭제되었습니다.");
      fetchDocs();
    } catch (err) {
      showMsg("err", String(err));
    } finally {
      setDeletingId(null);
    }
  };

  const handleCancelForm = () => {
    setShowForm(false);
    setForm(EMPTY_FORM);
    setEditingId(null);
  };

  const filtered = docs.filter((d) => {
    if (typeFilter !== "all" && d.type !== typeFilter) return false;
    if (search && !d.title.toLowerCase().includes(search.toLowerCase()) &&
        !(d.tags ?? "").toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const title = pageTitle ?? (defaultType === "report" ? "리포트" : "자료실");
  const subtitle = defaultType === "report"
    ? "투자 분석 리포트 관리"
    : "리포트, 아이디어, 메모, 뉴스 요약 관리";

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">{title}</h1>
          <p className="text-sm text-slate-400">{subtitle}</p>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="제목/태그 검색..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-slate-700 border border-slate-600 rounded-lg px-3 py-1.5 text-sm text-white
                       placeholder:text-slate-500 focus:outline-none focus:border-blue-500 w-44"
          />
          <button
            onClick={() => { setEditingId(null); setForm(EMPTY_FORM); setShowForm(!showForm); }}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-colors"
          >
            + 새 자료
          </button>
        </div>
      </div>

      {msg && (
        <div className={cn(
          "px-4 py-2 rounded-lg text-sm",
          msg.type === "ok" ? "bg-green-500/20 text-green-300" : "bg-red-500/20 text-red-300"
        )}>
          {msg.text}
        </div>
      )}

      {showForm && (
        <Card title={editingId !== null ? "자료 수정" : "새 자료 등록"}>
          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-slate-400 block mb-1">유형</label>
                <select
                  value={form.type}
                  onChange={(e) => setForm({ ...form, type: e.target.value })}
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-2 py-1.5
                             text-sm text-white focus:outline-none focus:border-blue-500"
                >
                  {DOC_TYPES.filter((t) => t.value !== "all").map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1">태그 (쉼표 구분)</label>
                <input
                  type="text"
                  placeholder="예: 미국,주식,분석"
                  value={form.tags}
                  onChange={(e) => setForm({ ...form, tags: e.target.value })}
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-2 py-1.5
                             text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1">제목 *</label>
              <input
                type="text"
                placeholder="자료 제목"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                required
                className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2
                           text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1">내용</label>
              <textarea
                rows={4}
                placeholder="자료 내용을 입력하세요..."
                value={form.content}
                onChange={(e) => setForm({ ...form, content: e.target.value })}
                className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2
                           text-sm text-white placeholder:text-slate-600 focus:outline-none
                           focus:border-blue-500 resize-none"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1">URL (선택)</label>
              <input
                type="url"
                placeholder="https://..."
                value={form.url}
                onChange={(e) => setForm({ ...form, url: e.target.value })}
                className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2
                           text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={handleCancelForm}
                className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 text-sm rounded-lg transition-colors"
              >
                취소
              </button>
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm rounded-lg transition-colors"
              >
                {saving ? "저장 중..." : editingId !== null ? "수정 저장" : "저장"}
              </button>
            </div>
          </form>
        </Card>
      )}

      <div className="flex flex-wrap gap-2">
        {DOC_TYPES.map((t) => (
          <button
            key={t.value}
            onClick={() => setTypeFilter(t.value)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5",
              typeFilter === t.value
                ? "bg-blue-600 text-white"
                : "bg-slate-700 text-slate-400 hover:bg-slate-600"
            )}
          >
            <span>{t.icon}</span>
            {t.label}
            <span className="text-slate-500 ml-0.5">
              ({t.value === "all" ? docs.length : docs.filter((d) => d.type === t.value).length})
            </span>
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-40 text-slate-500">로딩 중...</div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-40 gap-2 text-slate-500">
          <p>자료가 없습니다.</p>
          <button
            onClick={() => { setEditingId(null); setForm(EMPTY_FORM); setShowForm(true); }}
            className="text-sm text-blue-400 hover:text-blue-300"
          >
            첫 번째 자료 등록하기 →
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((doc) => {
            const typeInfo = DOC_TYPES.find((t) => t.value === doc.type) ?? DOC_TYPES[0];
            return (
              <Card key={doc.id}>
                <div className="flex items-start gap-2">
                  <span className="text-xl">{typeInfo.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-1">
                      <span className="text-[10px] bg-slate-700 text-slate-400 px-1.5 py-0.5 rounded">
                        {typeInfo.label}
                      </span>
                    </div>
                    <p className="text-sm font-semibold text-white truncate">{doc.title}</p>
                    {doc.content && (
                      <p className="text-xs text-slate-400 mt-1 line-clamp-2">{doc.content}</p>
                    )}
                    {doc.tags && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {doc.tags.split(",").map((tag) => (
                          <span key={tag} className="text-[10px] bg-blue-500/20 text-blue-400 px-1.5 py-0.5 rounded">
                            #{tag.trim()}
                          </span>
                        ))}
                      </div>
                    )}
                    {doc.url && (
                      <a
                        href={doc.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[10px] text-blue-400 hover:text-blue-300 mt-2 block truncate"
                      >
                        🔗 {doc.url}
                      </a>
                    )}
                    <p className="text-[10px] text-slate-600 mt-2">{doc.created_at}</p>
                    <div className="flex gap-3 mt-3 pt-2 border-t border-slate-700/50">
                      <button
                        onClick={() => handleEdit(doc)}
                        className="text-xs text-slate-400 hover:text-blue-400 transition-colors"
                      >
                        ✏️ 수정
                      </button>
                      <button
                        onClick={() => doc.id !== undefined && handleDelete(doc.id)}
                        disabled={deletingId === doc.id}
                        className="text-xs text-slate-400 hover:text-red-400 transition-colors disabled:opacity-50"
                      >
                        🗑️ {deletingId === doc.id ? "삭제 중..." : "삭제"}
                      </button>
                    </div>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
