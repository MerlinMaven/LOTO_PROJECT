import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  History,
  Info,
  LoaderCircle,
  RotateCcw,
  UploadCloud,
  WifiOff,
  ArrowRight,
  ShieldCheck,
} from "lucide-react";
import {
  getDocumentJob,
  listDocumentJobs,
  retryDocumentJob,
  submitPdfDocument,
  type DocumentJob,
} from "@/api/generation";

const MAX_PDF_BYTES = 20 * 1024 * 1024;
const ACTIVE_JOB_KEY = "smartloto_active_job_id";

const PROCESS_STEPS = [
  { id: "queued", label: "Document reçu par le serveur" },
  { id: "reading", label: "Extraction du texte et des schémas" },
  { id: "analyzing", label: "Analyse technique et structuration LOTO" },
  { id: "saving", label: "Validation et création du brouillon" },
  { id: "succeeded", label: "Brouillon prêt pour revue HSE" },
];

export function GenerateProcedure() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [networkWarning, setNetworkWarning] = useState<string | null>(null);
  const [job, setJob] = useState<DocumentJob | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  const [jobsHistory, setJobsHistory] = useState<DocumentJob[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  const redirectedRef = useRef(false);

  // Recharge l'historique des tâches depuis le backend
  const refreshHistory = useCallback(async () => {
    try {
      const history = await listDocumentJobs(15);
      setJobsHistory(history);
      return history;
    } catch {
      return [];
    }
  }, []);

  // Restauration de l'état au montage
  useEffect(() => {
    let isMounted = true;
    async function restoreActiveTask() {
      if (redirectedRef.current) return;
      const history = await refreshHistory();
      if (!isMounted || redirectedRef.current) return;

      const rememberedJobId = localStorage.getItem(ACTIVE_JOB_KEY);
      const activeJob = history.find((item) => item.status === "queued" || item.status === "running");
      const targetId = activeJob?.job_id || rememberedJobId;

      if (targetId) {
        try {
          const loaded = await getDocumentJob(targetId);
          if (!isMounted || redirectedRef.current) return;
          setJob(loaded);
          if (loaded.status === "queued" || loaded.status === "running") {
            setIsRunning(true);
            setElapsedSeconds(loaded.elapsed_seconds ?? 0);
          } else if (loaded.status === "succeeded") {
            localStorage.removeItem(ACTIVE_JOB_KEY);
            setIsRunning(false);
            redirectedRef.current = true;
            const targetProc = loaded.procedure_id || (loaded.result as Record<string, unknown> | undefined)?.procedure_id;
            if (targetProc) {
              navigate(`/procedures/${encodeURIComponent(String(targetProc))}`, { replace: true });
            }
          } else if (loaded.status === "failed") {
            setFileError(loaded.error || "Le traitement a échoué.");
            setIsRunning(false);
          }
        } catch {
          localStorage.removeItem(ACTIVE_JOB_KEY);
        }
      }
    }

    void restoreActiveTask();
    return () => {
      isMounted = false;
    };
  }, [refreshHistory, navigate]);

  // Chronomètre de durée écoulée pendant l'analyse active
  useEffect(() => {
    if (!isRunning) return;
    const interval = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [isRunning]);

  // Boucle de polling robuste : redirige instantanément vers la revue dès la réussite
  useEffect(() => {
    if (!job || !isRunning || redirectedRef.current) return;
    if (job.status !== "queued" && job.status !== "running") return;

    let isPolling = true;
    const intervalId = setInterval(async () => {
      if (!isPolling || redirectedRef.current) return;
      try {
        const updated = await getDocumentJob(job.job_id);
        if (!isPolling || redirectedRef.current) return;
        setNetworkWarning(null);
        setJob(updated);

        if (updated.status === "succeeded") {
          isPolling = false;
          clearInterval(intervalId);
          redirectedRef.current = true;
          setIsRunning(false);
          localStorage.removeItem(ACTIVE_JOB_KEY);
          void refreshHistory();
          void queryClient.invalidateQueries({ queryKey: ["procedures"] });

          // Redirection immédiate vers l'espace de revue HSE du brouillon
          const targetProc = updated.procedure_id || (updated.result as Record<string, unknown> | undefined)?.procedure_id;
          if (targetProc) {
            navigate(`/procedures/${encodeURIComponent(String(targetProc))}`, { replace: true });
          }
        } else if (updated.status === "failed") {
          isPolling = false;
          clearInterval(intervalId);
          setIsRunning(false);
          setFileError(updated.error || "Le traitement du document a échoué.");
          void refreshHistory();
        }
      } catch {
        if (!isPolling || redirectedRef.current) return;
        setNetworkWarning("Connexion au serveur momentanément interrompue, nouvelle tentative…");
      }
    }, 1500);

    return () => {
      isPolling = false;
      clearInterval(intervalId);
    };
  }, [job?.job_id, isRunning, job?.status, refreshHistory, queryClient, navigate]);

  const chooseFile = async (candidate?: File) => {
    if (!candidate) return;
    setIsRunning(false);
    setJob(null);
    setFileError(null);
    setNetworkWarning(null);
    setElapsedSeconds(0);
    localStorage.removeItem(ACTIVE_JOB_KEY);

    if (!candidate.name.toLowerCase().endsWith(".pdf") || (candidate.type && candidate.type !== "application/pdf")) {
      setFile(null);
      setFileError("Veuillez sélectionner un fichier au format PDF.");
      return;
    }
    if (candidate.size === 0) {
      setFile(null);
      setFileError("Le fichier PDF est vide.");
      return;
    }
    if (candidate.size > MAX_PDF_BYTES) {
      setFile(null);
      setFileError("Fichier trop volumineux. La taille maximale est de 20 Mo.");
      return;
    }

    setFile(candidate);
  };

  const runUploadAndAnalyze = async () => {
    if (!file || isRunning || isUploading) return;
    setIsUploading(true);
    setFileError(null);
    setNetworkWarning(null);
    setElapsedSeconds(0);

    try {
      const response = await submitPdfDocument(file);
      setIsUploading(false);
      setJob(response);
      localStorage.setItem(ACTIVE_JOB_KEY, response.job_id);

      if (response.status === "succeeded") {
        redirectedRef.current = true;
        localStorage.removeItem(ACTIVE_JOB_KEY);
        void queryClient.invalidateQueries({ queryKey: ["procedures"] });
        const targetProc = response.procedure_id || (response.result as Record<string, unknown> | undefined)?.procedure_id;
        if (targetProc) {
          navigate(`/procedures/${encodeURIComponent(String(targetProc))}`, { replace: true });
        }
      } else {
        setIsRunning(true);
      }
    } catch (err: unknown) {
      setIsUploading(false);
      setIsRunning(false);
      const msg = err instanceof Error ? err.message : "Échec de l'envoi du document.";
      setFileError(msg);
    }
  };

  const handleRetry = async () => {
    if (!job || isRunning) return;
    setFileError(null);
    setNetworkWarning(null);
    setElapsedSeconds(0);
    setIsRunning(true);

    try {
      const response = await retryDocumentJob(job.job_id);
      setJob(response);
      localStorage.setItem(ACTIVE_JOB_KEY, response.job_id);
    } catch (err: unknown) {
      setIsRunning(false);
      const msg = err instanceof Error ? err.message : "Impossible de relancer l'analyse.";
      setFileError(msg);
    }
  };

  const currentStageIndex = job
    ? PROCESS_STEPS.findIndex((s) => s.id === job.stage)
    : -1;

  return (
    <main className="mx-auto max-w-4xl space-y-6">
      {/* ── En-tête simplifié ──────────────────────────────────────────────── */}
      <header className="rounded-xl border border-slate-200/80 bg-white p-6 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
            <ShieldCheck className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">
              Générer une procédure LOTO
            </h1>
            <p className="mt-0.5 text-sm text-slate-500">
              Importez un dossier technique, manuel ou schéma industriel. L’analyse crée directement un brouillon prêt pour revue HSE.
            </p>
          </div>
        </div>
      </header>

      {/* ── Zone d'import PDF ───────────────────────────────────────────────── */}
      <section className="rounded-xl border border-slate-200/80 bg-white p-6 shadow-sm">
        <div
          role="button"
          tabIndex={0}
          aria-label="Zone de dépôt du document PDF"
          onClick={() => !isRunning && !isUploading && inputRef.current?.click()}
          onKeyDown={(e) => {
            if ((e.key === "Enter" || e.key === " ") && !isRunning && !isUploading) {
              e.preventDefault();
              inputRef.current?.click();
            }
          }}
          onDragOver={(e) => {
            e.preventDefault();
            if (!isRunning && !isUploading) setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragging(false);
            if (isRunning || isUploading) return;
            const dropped = e.dataTransfer.files?.[0];
            void chooseFile(dropped);
          }}
          className={`flex min-h-[180px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 text-center transition-all ${
            isDragging
              ? "border-blue-500 bg-blue-50/60"
              : isRunning || isUploading
                ? "cursor-not-allowed border-slate-200 bg-slate-50 opacity-70"
                : "border-slate-300 hover:border-blue-400 hover:bg-slate-50/60"
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            onChange={(e) => void chooseFile(e.target.files?.[0])}
            disabled={isRunning || isUploading}
          />

          <UploadCloud className={`h-10 w-10 ${file ? "text-blue-600" : "text-slate-400"}`} />

          {file ? (
            <div className="mt-3">
              <p className="font-semibold text-slate-800">{file.name}</p>
              <p className="text-xs text-slate-500">{(file.size / (1024 * 1024)).toFixed(2)} Mo · Cliquez pour changer de fichier</p>
            </div>
          ) : (
            <div className="mt-3">
              <p className="text-sm font-medium text-slate-700">
                Glissez votre fichier PDF ici, ou <span className="text-blue-600 underline">parcourez vos fichiers</span>
              </p>
              <p className="mt-1 text-xs text-slate-400">Schémas P&ID, manuels machine ou notices (max 20 Mo)</p>
            </div>
          )}
        </div>

        {fileError && (
          <div role="alert" className="mt-4 flex items-start gap-2.5 rounded-md border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
            <div className="flex-1">
              <p className="font-medium">{fileError}</p>
            </div>
          </div>
        )}

        {networkWarning && (
          <div role="status" className="mt-4 flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
            <WifiOff className="h-4 w-4 shrink-0 text-amber-600" />
            <span>{networkWarning}</span>
          </div>
        )}

        {/* Bouton d'action principal */}
        <div className="mt-5 flex items-center gap-3">
          <button
            type="button"
            onClick={() => void runUploadAndAnalyze()}
            disabled={!file || isRunning || isUploading}
            className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 py-3 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 transition-all"
          >
            {isUploading || isRunning ? (
              <LoaderCircle className="h-4 w-4 animate-spin" />
            ) : (
              <ArrowRight className="h-4 w-4" />
            )}
            {isUploading
              ? "Envoi du document…"
              : isRunning
                ? "Analyse en cours (redirection automatique dès fin)…"
                : "Lancer l'analyse et créer le brouillon"}
          </button>

          {job?.can_retry && !isRunning && (
            <button
              type="button"
              onClick={() => void handleRetry()}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              <RotateCcw className="h-4 w-4" />
              Relancer l'analyse
            </button>
          )}
        </div>

        {/* ── Suivi d'avancement clair ────────────────────────────────────── */}
        {isRunning && (
          <div className="mt-6 rounded-lg border border-blue-100 bg-blue-50/40 p-4">
            <div className="flex items-center justify-between text-xs text-slate-600">
              <span className="font-semibold text-blue-900">
                {job?.source_filename ? `Document : ${job.source_filename}` : "Traitement serveur en cours"}
              </span>
              <span className="font-mono text-slate-500">
                Temps écoulé : {elapsedSeconds}s
              </span>
            </div>

            {elapsedSeconds > 25 && (
              <div className="mt-3 flex items-center gap-2 rounded bg-blue-100/70 px-3 py-2 text-xs text-blue-900">
                <Info className="h-4 w-4 shrink-0 text-blue-700" />
                <span>Le document est dense, l'analyse multimodale continue en tâche de fond… Vous serez redirigé automatiquement.</span>
              </div>
            )}

            <ol aria-live="polite" className="mt-4 space-y-2.5">
              {PROCESS_STEPS.map((step, idx) => {
                const isDone = currentStageIndex > idx;
                const isActive = currentStageIndex === idx;

                return (
                  <li key={step.id} className="flex items-center gap-3 text-xs">
                    {isDone ? (
                      <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                    ) : isActive ? (
                      <LoaderCircle className="h-4 w-4 animate-spin text-blue-600 shrink-0" />
                    ) : (
                      <span className="h-4 w-4 rounded-full border border-slate-300 shrink-0" />
                    )}
                    <span className={isActive ? "font-bold text-blue-900" : isDone ? "font-medium text-slate-700" : "text-slate-400"}>
                      {step.label}
                    </span>
                  </li>
                );
              })}
            </ol>
          </div>
        )}
      </section>

      {/* ── Historique des analyses récentes ─────────────────────────────────── */}
      {jobsHistory.length > 0 && (
        <section className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-sm">
          <button
            type="button"
            onClick={() => setShowHistory((prev) => !prev)}
            className="flex w-full items-center justify-between text-sm font-semibold text-slate-800"
          >
            <div className="flex items-center gap-2">
              <History className="h-4 w-4 text-slate-500" />
              <span>Historique des analyses récentes ({jobsHistory.length})</span>
            </div>
            {showHistory ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronDown className="h-4 w-4 text-slate-400" />}
          </button>

          {showHistory && (
            <ul className="mt-3 divide-y divide-slate-100 text-xs">
              {jobsHistory.map((item) => {
                const dateStr = item.created_at ? new Date(item.created_at).toLocaleString("fr-FR") : "";
                const targetProc = item.procedure_id;

                return (
                  <li
                    key={item.job_id}
                    className="flex items-center justify-between py-2.5"
                  >
                    <div className="min-w-0 pr-3">
                      <p className="truncate font-medium text-slate-800">
                        {item.source_filename || "Document PDF"}
                      </p>
                      <p className="text-slate-400">{dateStr}</p>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${
                          item.status === "succeeded"
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : item.status === "failed"
                              ? "bg-rose-50 text-rose-700 border border-rose-200"
                              : "bg-blue-50 text-blue-700 border border-blue-200"
                        }`}
                      >
                        {item.status === "succeeded"
                          ? "Terminé"
                          : item.status === "failed"
                            ? "Échec"
                            : "En cours"}
                      </span>

                      {item.status === "succeeded" && targetProc ? (
                        <button
                          type="button"
                          onClick={() => navigate(`/procedures/${encodeURIComponent(String(targetProc))}`)}
                          className="flex items-center gap-1 rounded border border-blue-200 bg-blue-50 px-2.5 py-1 text-blue-700 hover:bg-blue-100 font-semibold text-[11px]"
                        >
                          <span>Ouvrir la revue</span>
                          <ArrowRight className="h-3 w-3" />
                        </button>
                      ) : null}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      )}
    </main>
  );
}
