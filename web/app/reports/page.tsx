// app/reports/page.tsx
// 리포트 페이지 — 자료실 중 "report" 유형만 필터링하여 표시
import DocumentsPageClient from "../documents/DocumentsPageClient";

export default function ReportsPage() {
  return (
    <DocumentsPageClient
      defaultType="report"
      pageTitle="리포트"
    />
  );
}

