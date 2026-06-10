import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { clsx } from "clsx";
import { runGeneration, type GenerationRunResponse } from "@/api/generation";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import type { ApiError } from "@/types/api";

type Provider = "stub" | "claude";
type SourceType = "text" | "image";

const PROVIDER_OPTIONS: { value: Provider; label: string; description: string }[] = [
  {
    value: "stub",
    label: "Stub (offline)",
    description: "No API key required — returns a template skeleton for testing.",
  },
  {
    value: "claude",
    label: "Claude (Anthropic)",
    description: "Requires ANTHROPIC_API_KEY in the Authoring Service .env.",
  },
];

export function GenerateProcedure() {
  const navigate = useNavigate();

  const [machineId, setMachineId] = useState("SIM-CHP-2026");
  const [machineName, setMachineName] = useState("Compresseur HP");
  const [requestedBy, setRequestedBy] = useState("");
  const [components, setComponents] = useState(
    "Disjoncteur électrique principal (noir)\nCadenas rouge sur moraillon électrique\nVanne de décharge de pression (rouge)\nCadenas jaune sur la vanne de fluide",
  );
  const [provider, setProvider] = useState<Provider>("stub");
  const [sourceType, setSourceType] = useState<SourceType>("text");
  const [imageBase64, setImageBase64] = useState<string | undefined>();
  const [imagePreview, setImagePreview] = useState<string | undefined>();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const mutation = useMutation({
    mutationFn: runGeneration,
  });

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const result = ev.target?.result as string;
      setImagePreview(result);
      // Strip data URL prefix for API
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold text-steel-800">Generate Procedure</h2>
        <p className="text-sm text-steel-500">
          AI-assisted LOTO procedure generation from machine metadata. The
          generated draft will appear in the Procedures list for HSE review.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Left: inputs */}
        <div className="surface space-y-4 p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-steel-500">
            Machine Parameters
          </p>

          <div className="space-y-3">
            <div>
              <label className="field-label">Machine ID</label>
              <input
                className="field-input"
                value={machineId}
                onChange={(e) => setMachineId(e.target.value)}
                placeholder="e.g. COMPRESSEUR_A1"
              />
            </div>
            <div>
              <label className="field-label">Machine Name</label>
              <input
                className="field-input"
                value={machineName}
                onChange={(e) => setMachineName(e.target.value)}
                placeholder="e.g. Compresseur HP Ligne A"
              />
            </div>
            <div>
              <label className="field-label">HSE Engineer</label>
              <input
                className="field-input"
                value={requestedBy}
                onChange={(e) => setRequestedBy(e.target.value)}
                placeholder="Your username or name"
              />
            </div>
            <div>
              <label className="field-label">
                Energy Sources & Components to Isolate
              </label>
              <textarea
                className="field-input min-h-[120px] resize-y"
                value={components}
                onChange={(e) => setComponents(e.target.value)}
                placeholder="One component per line&#10;e.g. Main electrical breaker (black)&#10;Red padlock on moraillon"
              />
              <p className="mt-1 text-xs text-steel-400">
                One component per line. Include colour and position for better
                YOLO-World prompts.
              </p>
            </div>
          </div>

          {/* Source type */}
          <div>
            <p className="field-label mb-2">Generation Mode</p>
            <div className="flex gap-3">
              {(["text", "image"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setSourceType(t)}
                  className={clsx(
                    "rounded-lg border px-3 py-2 text-sm font-medium transition",
                    sourceType === t
                      ? "border-steel-700 bg-steel-700 text-white"
                      : "border-steel-200 text-steel-600 hover:border-steel-400",
                  )}
                >
                  {t === "text" ? "Text only" : "Text + Image (VLLM)"}
                </button>
              ))}
            </div>
          </div>

          {sourceType === "image" && (
            <div>
              <label className="field-label">Machine Photo</label>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/png,image/jpeg,image/jpg"
                className="hidden"
                onChange={handleImageUpload}
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                className="w-full rounded-lg border-2 border-dashed border-steel-200 py-4 text-sm text-steel-500 hover:border-steel-400 hover:text-steel-700 transition"
              >
                {imagePreview ? "Click to replace photo" : "Click to upload machine photo"}
              </button>
              {imagePreview && (
                <img
                  src={imagePreview}
                  alt="Machine preview"
                  className="mt-2 max-h-40 rounded-lg object-contain"
                />
              )}
            </div>
          )}

          {/* Provider */}
          <div>
            <p className="field-label mb-2">LLM Provider</p>
            <div className="space-y-2">
              {PROVIDER_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setProvider(opt.value)}
                  className={clsx(
                    "flex w-full items-start gap-3 rounded-lg border p-3 text-left transition",
                    provider === opt.value
                      ? "border-steel-700 bg-steel-50"
                      : "border-steel-200 hover:border-steel-300",
                  )}
                >
                  <span
                    className={clsx(
                      "mt-0.5 h-4 w-4 shrink-0 rounded-full border-2",
                      provider === opt.value
                        ? "border-steel-700 bg-steel-700"
                        : "border-steel-300",
                    )}
                  />
                  <span>
                    <span className="block text-sm font-medium text-steel-800">
                      {opt.label}
                    </span>
                    <span className="text-xs text-steel-500">{opt.description}</span>
                  </span>
                </button>
              ))}
            </div>
          </div>

          <Button
            variant="primary"
            className="w-full"
            onClick={handleGenerate}
            loading={isRunning}
            disabled={
              !machineId.trim() ||
              !requestedBy.trim() ||
              (sourceType === "image" && !imageBase64)
            }
          >
            {isRunning ? "Generating…" : "Generate LOTO Procedure"}
          </Button>

          {mutation.isError && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-hazard">
              {(mutation.error as ApiError)?.message ?? "Generation failed."}
            </div>
          )}
        </div>

        {/* Right: result */}
        <div className="space-y-4">
          {isRunning && (
            <div className="surface flex items-center justify-center py-20">
              <Spinner label="Running generation pipeline…" />
            </div>
          )}

          {result && !isRunning && (
            <>
              {/* Status banner */}
              <div
                className={clsx(
                  "rounded-lg border px-4 py-3",
                  result.is_publishable
                    ? "border-emerald-200 bg-emerald-50"
                    : "border-amber-200 bg-amber-50",
                )}
              >
                <p
                  className={clsx(
                    "text-sm font-semibold",
                    result.is_publishable ? "text-emerald-700" : "text-amber-700",
                  )}
                >
                  {result.is_publishable
                    ? "Pipeline completed — procedure is publishable"
                    : "Pipeline completed with errors — review required before publishing"}
                </p>
                <p className="mt-0.5 text-xs text-steel-500">
                  Job {result.job_id.slice(0, 8)} · Provider:{" "}
                  {result.llm_provider ?? "unknown"}
                </p>
              </div>

              {/* Validation errors */}
              {result.validation_errors.length > 0 && (
                <div className="surface p-4">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-hazard">
                    {result.validation_errors.length} Validation Error
                    {result.validation_errors.length > 1 ? "s" : ""}
                  </p>
                  <ul className="space-y-1">
                    {result.validation_errors.map((e, i) => (
                      <li key={i} className="text-xs text-steel-700">
                        <span className="font-medium text-hazard">[{e.code}]</span>{" "}
                        {e.message}
                        {e.field_path && (
                          <code className="ml-1 text-[10px] text-steel-400">
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
                <div className="surface p-4">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-amber-600">
                    {result.validation_warnings.length} Warning
                    {result.validation_warnings.length > 1 ? "s" : ""}
                  </p>
                  <ul className="space-y-1">
                    {result.validation_warnings.map((w, i) => (
                      <li key={i} className="text-xs text-steel-700">
                        <span className="font-medium text-amber-600">[{w.code}]</span>{" "}
                        {w.message}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Generation notes */}
              {result.generation_notes.length > 0 && (
                <div className="surface p-4">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-steel-500">
                    Generation Notes
                  </p>
                  <ul className="space-y-1">
                    {result.generation_notes.map((note, i) => (
                      <li key={i} className="text-xs text-steel-600">
                        · {note}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Workflow preview */}
              <div className="surface p-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-steel-500">
                  Generated Workflow (JSON Preview)
                </p>
                <pre className="max-h-72 overflow-auto rounded bg-steel-50 p-3 text-[10px] text-steel-700">
                  {JSON.stringify(result.workflow_definition, null, 2)}
                </pre>
              </div>

              <Button
                variant="secondary"
                className="w-full"
                onClick={() => navigate("/procedures")}
              >
                Back to Procedures list
              </Button>
            </>
          )}

          {!result && !isRunning && (
            <div className="surface flex flex-col items-center justify-center py-20 text-center">
              <p className="text-sm font-medium text-steel-700">
                Fill in the machine parameters and click Generate.
              </p>
              <p className="mt-1 text-xs text-steel-400">
                The result will appear here once the pipeline completes.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
