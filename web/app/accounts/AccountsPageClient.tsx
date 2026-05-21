// app/accounts/AccountsPageClient.tsx
"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { AccountSummary } from "@/lib/types";
import Card from "@/components/ui/Card";
import { cn, formatKRW } from "@/lib/utils";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Position {
  id: number;
  ticker: string;
  name: string;
  quantity: number;
  avg_price: number;
  current_price: number;
  market_value: number;
  profit: number;
}

export default function AccountsPageClient() {
  const [accounts, setAccounts] = useState<AccountSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<number | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [posLoading, setPosLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const fetchAccounts = () => {
    setLoading(true);
    api.getDashboardSummary()
      .then((data) => setAccounts(data.accounts ?? []))
      .catch(() => setAccounts([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchAccounts();
  }, []);

  const handleSelectAccount = async (id: number) => {
    if (selected === id) {
      setSelected(null);
      setPositions([]);
      return;
    }
    setSelected(id);
    setPosLoading(true);
    try {
      const res = await fetch(`${BASE_URL}/api/accounts/${id}/positions`);
      const data = await res.json();
      setPositions(data);
    } catch {
      setPositions([]);
    } finally {
      setPosLoading(false);
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadMsg(null);
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch(`${BASE_URL}/api/accounts/upload-csv`, {
        method: "POST",
        body: form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail ?? "업로드 실패");
      setUploadMsg({ type: "ok", text: `${data.inserted}개 종목 업로드 완료` });
      fetchAccounts();
    } catch (err) {
      setUploadMsg({ type: "err", text: String(err) });
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const totalValue = accounts.reduce((s, a) => s + a.value, 0);
  const totalProfit = accounts.reduce((s, a) => s + a.profit, 0);

  return (
    <div className="p-6 space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">계좌 현황</h1>
          <p className="text-sm text-slate-400">연결된 투자 계좌 및 보유 종목</p>
        </div>
        <div className="flex items-center gap-3">
          <label className={cn(
            "cursor-pointer px-3 py-2 rounded-lg text-sm font-medium transition-colors",
            uploading ? "bg-slate-600 text-slate-400" : "bg-blue-600 hover:bg-blue-700 text-white"
          )}>
            {uploading ? "업로드 중..." : "CSV 업로드"}
            <input
              ref={fileRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={handleUpload}
              disabled={uploading}
            />
          </label>
          <a
            href="data:text/csv;charset=utf-8,account_name,ticker,name,quantity,avg_price,current_price%0A한국투자,005930,삼성전자,100,70000,75000"
            download="sample_holdings.csv"
            className="px-3 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 text-sm rounded-lg transition-colors"
          >
            샘플 다운로드
          </a>
        </div>
      </div>

      {uploadMsg && (
        <div className={cn(
          "px-4 py-2 rounded-lg text-sm",
          uploadMsg.type === "ok" ? "bg-green-500/20 text-green-300" : "bg-red-500/20 text-red-300"
        )}>
          {uploadMsg.text}
        </div>
      )}

      {/* 요약 KPI */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <p className="text-xs text-slate-400">총 자산</p>
          <p className="text-xl font-bold text-white mt-1">{formatKRW(totalValue)}</p>
        </Card>
        <Card>
          <p className="text-xs text-slate-400">총 손익</p>
          <p className={cn("text-xl font-bold mt-1", totalProfit >= 0 ? "text-green-400" : "text-red-400")}>
            {totalProfit >= 0 ? "+" : ""}{formatKRW(totalProfit)}
          </p>
        </Card>
        <Card>
          <p className="text-xs text-slate-400">계좌 수</p>
          <p className="text-xl font-bold text-white mt-1">{accounts.length}개</p>
        </Card>
      </div>

      {/* 계좌 목록 */}
      {loading ? (
        <div className="flex items-center justify-center h-40 text-slate-500">로딩 중...</div>
      ) : (
        <Card title="계좌 목록">
          <div className="divide-y divide-slate-700">
            {accounts.map((acct) => (
              <div key={acct.id}>
                <button
                  className="w-full flex items-center justify-between py-3 hover:bg-slate-700/30 rounded px-2 transition-colors"
                  onClick={() => handleSelectAccount(acct.id)}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-blue-600/30 flex items-center justify-center text-blue-400 text-sm font-bold">
                      {acct.name.charAt(0)}
                    </div>
                    <div className="text-left">
                      <p className="text-sm font-semibold text-white">{acct.name}</p>
                      <p className="text-xs text-slate-500">{acct.type ?? "일반계좌"}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-bold text-white">{formatKRW(acct.value)}</p>
                    <p className={cn("text-xs", acct.profit >= 0 ? "text-green-400" : "text-red-400")}>
                      {acct.profit >= 0 ? "▲" : "▼"} {formatKRW(Math.abs(acct.profit))}
                      <span className="text-slate-500 ml-1">({acct.profitRate >= 0 ? "+" : ""}{acct.profitRate.toFixed(2)}%)</span>
                    </p>
                  </div>
                </button>

                {/* 보유 종목 드롭다운 */}
                {selected === acct.id && (
                  <div className="mx-2 mb-3 bg-slate-700/30 rounded-lg overflow-hidden">
                    {posLoading ? (
                      <div className="py-4 text-center text-sm text-slate-500">로딩 중...</div>
                    ) : positions.length === 0 ? (
                      <div className="py-4 text-center text-sm text-slate-500">
                        보유 종목 없음 (CSV 업로드로 추가)
                      </div>
                    ) : (
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="text-slate-500 border-b border-slate-600">
                            <th className="text-left px-3 py-2">종목</th>
                            <th className="text-right px-3 py-2">수량</th>
                            <th className="text-right px-3 py-2">평균가</th>
                            <th className="text-right px-3 py-2">현재가</th>
                            <th className="text-right px-3 py-2">평가금액</th>
                            <th className="text-right px-3 py-2">손익</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-700/50">
                          {positions.map((p) => (
                            <tr key={p.id} className="hover:bg-slate-700/20">
                              <td className="px-3 py-2">
                                <p className="text-white font-medium">{p.name}</p>
                                <p className="text-slate-500">{p.ticker}</p>
                              </td>
                              <td className="px-3 py-2 text-right text-slate-300">{p.quantity.toLocaleString()}</td>
                              <td className="px-3 py-2 text-right text-slate-300">{p.avg_price?.toLocaleString()}</td>
                              <td className="px-3 py-2 text-right text-slate-300">{p.current_price?.toLocaleString()}</td>
                              <td className="px-3 py-2 text-right text-white">{formatKRW(p.market_value)}</td>
                              <td className={cn("px-3 py-2 text-right", p.profit >= 0 ? "text-green-400" : "text-red-400")}>
                                {p.profit >= 0 ? "+" : ""}{formatKRW(p.profit)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
          {accounts.length === 0 && (
            <div className="py-8 text-center text-slate-500">
              CSV 업로드로 계좌 및 보유 종목을 추가하세요.
            </div>
          )}
        </Card>
      )}

      {/* CSV 형식 안내 */}
      <Card title="CSV 형식 안내">
        <p className="text-xs text-slate-400 mb-2">아래 형식으로 CSV 파일을 작성하세요.</p>
        <pre className="bg-slate-800 rounded-lg p-3 text-xs text-slate-300 overflow-x-auto">
{`account_name,ticker,name,quantity,avg_price,current_price
한국투자,005930,삼성전자,100,70000,75000
한국투자,000660,SK하이닉스,50,120000,135000
미국주식,AAPL,Apple Inc,10,170.00,185.00`}
        </pre>
      </Card>
    </div>
  );
}
