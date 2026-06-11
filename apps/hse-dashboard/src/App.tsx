import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { DashboardHome } from "@/pages/DashboardHome";
import { DraftReview } from "@/pages/DraftReview";
import { GenerateProcedure } from "@/pages/GenerateProcedure";
import { InterventionMonitor } from "@/pages/InterventionMonitor";
import { NotFound } from "@/pages/NotFound";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/procedures" replace />} />
        <Route path="/procedures" element={<DashboardHome />} />
        <Route path="/procedures/:procedureId" element={<DraftReview />} />
        <Route path="/generate" element={<GenerateProcedure />} />
        <Route path="/interventions" element={<InterventionMonitor />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </AppShell>
  );
}
