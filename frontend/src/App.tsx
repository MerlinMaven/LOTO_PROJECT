import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { DashboardHome } from "@/pages/DashboardHome";
import { DraftReview } from "@/pages/DraftReview";
import { NotFound } from "@/pages/NotFound";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/procedures" replace />} />
        <Route path="/procedures" element={<DashboardHome />} />
        <Route path="/procedures/:procedureId" element={<DraftReview />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </AppShell>
  );
}
