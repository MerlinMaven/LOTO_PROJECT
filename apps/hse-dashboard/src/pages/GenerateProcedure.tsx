import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import { runGeneration } from "@/api/generation";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import type { ApiError } from "@/types/api";
import {
  Zap,
  Cpu,
  FileText,
  Image,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Info,
  ArrowRight,
  UploadCloud,
  ChevronRight,
} from "lucide-react";

type Provider = "openrouter" | "mistral" | "groq" | "vllm" | "stub";
type SourceType = "text" | "image";

const PROVIDER_OPTIONS: { value: Provider; label: string; description: string }[] = [
  {
    value: "openrouter",
    label: "OpenRouter (Recommandé)",
    description: "Clé OPENROUTER_API_KEY. Modèle par défaut : Qwen 2.5 7B. Vision via Qwen-VL.",
  },
  {
    value: "mistral",
    label: "Mistral AI",
    description: "Clé MISTRAL_API_KEY. Rapide et économique pour l'extraction JSON structurée.",
  },
  {
    value: "groq",
    label: "Groq (LLaMA 3 70B)",
    description: "Clé GROQ_API_KEY. Inférence ultra-rapide avec LLaMA 3 70B.",
  },
  {
    value: "vllm",
    label: "vLLM (Auto-hébergé)",
    description: "Utilise VLLM_BASE_URL. Votre propre serveur GPU. Supporte texte et vision.",
  },
  {
    value: "stub",
    label: "Stub (Mock — sans clé API)",
    description: "Retourne des données mock instantanées. Pour tests UI uniquement.",
  },
];

export function GenerateProcedure() {
  const navigate = useNavigate();

  const [machineId, setMachineId] = useState("");
  const [machineName, setMachineName] = useState("");
  const [requestedBy, setRequestedBy] = useState("");
  const [components, setComponents] = useState("");
  const [provider, setProvider] = useState<Provider>("openrouter");
  const [sourceType, setSourceType] = useState<SourceType>("text");
  const [imageBase64, setImageBase64] = useState<string | undefined>();
  const [imagePreview, setImagePreview] = useState<string | undefined>();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: runGeneration,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["procedures"] });
      if (data.procedure_id) {
        navigate(`/procedures/${data.procedure_id}`);
      } else {
        navigate("/procedures");
      }
    },
  });

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const result = ev.target?.result as string;
      setImagePreview(result);
      const b64 = result.includes(",") ? result.split(",")[1] : result;
      setImageBase64(b64);
    };
    reader.readAsDataURL(file);
  };

  const handleGenerate = () => {
    if (!requestedBy.trim()) return;
    if (sourceType === "image" && !imageBase64) return;
    mutation.mutate({
      machine_id: machineId.trim(),
      machine_name: machineName.trim(),
      components: components.trim(),
      requested_by: requestedBy.trim(),
      source_type: sourceType,
      image_base64: imageBase64,
      provider,
    });
  };

  const result = mutation.data;
  const isRunning = mutation.isPending;
  const canSubmit = !!machineId.trim() && !!requestedBy.trim() && !(sourceType === "image" && !imageBase64);

  return (
    <div className="space-y-5">

      {/* ── Page header ───────────────────────────────────────────────── */}
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-slate-200 bg-white shadow-sm">
          <Zap className="h-[18px] w-[18px] text-slate-600" strokeWidth={2} />
        </div>
        <div>
          <h2 className="text-base font-semibold text-slate-900">
            Générer une procédure LOTO
          </h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Génération assistée par IA à partir des métadonnées machine. Le brouillon apparaîtra dans la liste des procédures pour validation HSE.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">

        {/* ── Left: form ──────────────────────────────────────────────── */}
        <div className="space-y-5">

          {/* Machine parameters */}
          <div className="rounded-md border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center gap-2">
              <Cpu className="h-4 w-4 text-slate-500" strokeWidth={2} />
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Paramètres machine
              </span>
            </div>

            <div className="space-y-3.5">
              <FormField label="Machine ID" required>
                <input
                  className={inputCls}
                  value={machineId}
                  onChange={(e) => setMachineId(e.target.value)}
                  placeholder="ex. COMPRESSEUR_A1"
                />
              </FormField>

              <FormField label="Nom de la machine">
                <input
                  className={inputCls}
                  value={machineName}
                  onChange={(e) => setMachineName(e.target.value)}
                  placeholder="ex. Compresseur HP Ligne A"
                />
              </FormField>

              <FormField label="Ingénieur HSE" required>
                <input
                  className={inputCls}
                  value={requestedBy}
                  onChange={(e) => setRequestedBy(e.target.value)}
                  placeholder="Votre nom ou identifiant"
                />
              </FormField>

              <FormField
                label="Sources d'énergie & composants à isoler"
                hint="Un composant par ligne. Incluez couleur et position pour de meilleurs prompts YOLO-World."
              >
                <textarea
                  className={clsx(inputCls, "min-h-[108px] resize-y")}
                  value={components}
                  onChange={(e) => setComponents(e.target.value)}
                  placeholder={"Disjoncteur principal (noir)\nCadenas rouge sur moraillon\nVanne pneumatique V-12"}
                />
              </FormField>
            </div>
          </div>

          {/* Generation mode */}
          <div className="rounded-md border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center gap-2">
              <FileText className="h-4 w-4 text-slate-500" strokeWidth={2} />
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Mode de génération
              </span>
            </div>

            <div className="flex gap-2.5">
              {(["text", "image"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setSourceType(t)}
                  className={clsx(
                    "flex items-center gap-2 rounded-md border px-3.5 py-2 text-xs font-semibold transition-all duration-150",
                    sourceType === t
                      ? "border-blue-600 bg-blue-600 text-white shadow-sm"
                      : "border-slate-200 text-slate-600 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700",
                  )}
                >
                  {t === "text" ? <FileText className="h-3.5 w-3.5" /> : <Image className="h-3.5 w-3.5" />}
                  {t === "text" ? "Texte uniquement" : "Texte + Image (VLLM)"}
                </button>
              ))}
            </div>

            {sourceType === "image" && (
              <div className="mt-3.5">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/png,image/jpeg,image/jpg"
                  className="hidden"
                  onChange={handleImageUpload}
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className={clsx(
                    "flex w-full flex-col items-center gap-2 rounded-md border-2 border-dashed py-5 text-xs font-medium transition-all duration-150",
                    imagePreview
                      ? "border-blue-300 bg-blue-50 text-blue-700"
                      : "border-slate-200 text-slate-400 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-600",
                  )}
                >
                  <UploadCloud className="h-5 w-5" strokeWidth={1.5} />
                  {imagePreview ? "Cliquer pour remplacer la photo" : "Cliquer pour téléverser la photo machine"}
                </button>
                {imagePreview && (
                  <img
                    src={imagePreview}
                    alt="Aperçu machine"
                    className="mt-2.5 max-h-40 w-full rounded-md border border-slate-200 object-contain"
                  />
                )}
              </div>
            )}
          </div>

          {/* LLM Provider */}
          <div className="rounded-md border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center gap-2">
              <Cpu className="h-4 w-4 text-slate-500" strokeWidth={2} />
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Fournisseur LLM
              </span>
            </div>

            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value as Provider)}
              className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            >
              {PROVIDER_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>

            {PROVIDER_OPTIONS.find((o) => o.value === provider) && (
              <p className="mt-2 text-sm text-gray-500">
                {PROVIDER_OPTIONS.find((o) => o.value === provider)!.description}
              </p>
            )}
          </div>

          {/* Submit */}
          <button
            onClick={handleGenerate}
            disabled={isRunning || !canSubmit}
            className={clsx(
              "flex w-full items-center justify-center gap-2 rounded-md px-5 py-3 text-sm font-semibold shadow-sm transition-all duration-150",
              canSubmit && !isRunning
                ? "bg-blue-600 text-white hover:bg-blue-700"
                : "cursor-not-allowed bg-slate-100 text-slate-400",
            )}
          >
            {isRunning ? (
              <>
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Génération en cours…
              </>
            ) : (
              <>
                <Zap className="h-4 w-4" strokeWidth={2.5} />
                Générer la procédure LOTO
                <ChevronRight className="h-4 w-4 opacity-70" />
              </>
            )}
          </button>

          {mutation.isError && (
            <div className="flex items-start gap-2.5 rounded-md border border-rose-200 bg-rose-50 px-4 py-3">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
              <p className="text-sm text-rose-700">
                {(mutation.error as ApiError)?.message ?? "La génération a échoué."}
              </p>
            </div>
          )}
        </div>

        {/* ── Right: result ───────────────────────────────────────────── */}
        <div className="space-y-4">

          {isRunning && (
            <div className="flex min-h-[200px] flex-col items-center justify-center rounded-md border border-slate-200 bg-white p-10 shadow-sm">
              <Spinner label="Exécution du pipeline de génération…" />
            </div>
          )}

          {result && !isRunning && (
            <>
              {/* Status banner */}
              <div
                className={clsx(
                  "flex items-start gap-3 rounded-md border px-4 py-3 shadow-sm",
                  result.is_publishable
                    ? "border-emerald-200 bg-emerald-50"
                    : "border-amber-200 bg-amber-50",
                )}
              >
                {result.is_publishable
                  ? <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
                  : <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
                }
                <div>
                  <p className={clsx(
                    "text-sm font-semibold",
                    result.is_publishable ? "text-emerald-700" : "text-amber-700",
                  )}>
                    {result.is_publishable
                      ? "Pipeline terminé — procédure publiable"
                      : "Pipeline terminé avec erreurs — revue requise avant publication"}
                  </p>
                  <p className="mt-0.5 text-[11px] text-slate-500">
                    Job <code className="font-mono">{result.job_id.slice(0, 8)}</code>
                    {" · "}Fournisseur : {result.llm_provider ?? "inconnu"}
                  </p>
                </div>
              </div>

              {/* Validation errors */}
              {result.validation_errors.length > 0 && (
                <div className="rounded-md border border-rose-200 bg-white p-4 shadow-sm">
                  <p className="mb-2.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-rose-600">
                    <AlertCircle className="h-3.5 w-3.5" />
                    {result.validation_errors.length} erreur{result.validation_errors.length > 1 ? "s" : ""} de validation
                  </p>
                  <ul className="space-y-1.5">
                    {result.validation_errors.map((e, i) => (
                      <li key={i} className="text-xs text-slate-700">
                        <span className="font-mono font-semibold text-rose-600">[{e.code}]</span>{" "}
                        {e.message}
                        {e.field_path && (
                          <code className="ml-1.5 rounded bg-slate-100 px-1 text-[10px] text-slate-500">
                            {e.field_path}
                          </code>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Validation warnings */}
              {result.validation_warnings.length > 0 && (
                <div className="rounded-md border border-amber-200 bg-white p-4 shadow-sm">
                  <p className="mb-2.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-amber-600">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    {result.validation_warnings.length} avertissement{result.validation_warnings.length > 1 ? "s" : ""}
                  </p>
                  <ul className="space-y-1.5">
                    {result.validation_warnings.map((w, i) => (
                      <li key={i} className="text-xs text-slate-700">
                        <span className="font-mono font-semibold text-amber-600">[{w.code}]</span>{" "}
                        {w.message}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Generation notes */}
              {result.generation_notes.length > 0 && (
                <div className="rounded-md border border-slate-200 bg-white p-4 shadow-sm">
                  <p className="mb-2.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                    <Info className="h-3.5 w-3.5" />
                    Notes de génération
                  </p>
                  <ul className="space-y-1">
                    {result.generation_notes.map((note, i) => (
                      <li key={i} className="flex items-start gap-1.5 text-xs text-slate-600">
                        <span className="mt-0.5 text-slate-300">·</span>
                        {note}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Workflow JSON preview */}
              <div className="rounded-md border border-slate-200 bg-white p-4 shadow-sm">
                <p className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Workflow généré (aperçu JSON)
                </p>
                <pre className="max-h-72 overflow-auto rounded-md bg-slate-50 p-3 text-[10px] leading-relaxed text-slate-700">
                  {JSON.stringify(result.workflow_definition, null, 2)}
                </pre>
              </div>

              <button
                onClick={() => navigate("/procedures")}
                className="flex w-full items-center justify-center gap-2 rounded-md border border-slate-200 bg-white px-5 py-2.5 text-xs font-semibold text-slate-700 shadow-sm transition-all hover:border-slate-300 hover:bg-slate-50"
              >
                Retour à la liste des procédures
                <ArrowRight className="h-3.5 w-3.5 text-slate-400" />
              </button>
            </>
          )}

          {!result && !isRunning && (
            <div className="flex min-h-[200px] flex-col items-center justify-center rounded-md border border-dashed border-slate-200 bg-white p-10 text-center">
              <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-slate-100">
                <Zap className="h-5 w-5 text-slate-400" strokeWidth={1.5} />
              </div>
              <p className="text-sm font-medium text-slate-600">
                Renseignez les paramètres machine et cliquez sur Générer.
              </p>
              <p className="mt-1 text-xs text-slate-400">
                Le résultat apparaîtra ici une fois le pipeline terminé.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const inputCls =
  "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all";

function FormField({
  label,
  required,
  hint,
  children,
}: {
  label: string;
  required?: boolean;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1 flex items-center gap-1 text-xs font-semibold text-slate-700">
        {label}
        {required && <span className="text-rose-500">*</span>}
      </label>
      {children}
      {hint && <p className="mt-1 text-[11px] text-slate-400">{hint}</p>}
    </div>
  );
}
