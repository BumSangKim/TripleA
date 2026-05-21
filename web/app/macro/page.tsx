// app/macro/page.tsx
import MacroPageClient from "./MacroPageClient";

export const revalidate = 60;

export default function MacroPage() {
  return <MacroPageClient />;
}
