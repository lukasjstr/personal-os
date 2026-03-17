"use client";

import { useState, useCallback, useRef } from "react";
import { Upload, FileUp, Check, AlertCircle, X } from "lucide-react";
import { api } from "@/lib/api";

type ImportStatus = "idle" | "uploading" | "success" | "error";

interface ImportResult {
  days_imported: number;
  total_days_in_file: number;
  kr_updates: string[];
}

export default function HealthImport() {
  const [status, setStatus] = useState<ImportStatus>("idle");
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(async (file: File) => {
    setStatus("uploading");
    setError("");
    setResult(null);

    try {
      const isZip = file.name.endsWith(".zip") || file.type === "application/zip";
      const isCsv = file.name.endsWith(".csv") || file.type === "text/csv";

      let res;
      if (isZip) {
        res = await api.importAppleHealth(file);
      } else if (isCsv) {
        res = await api.importHealthCsv(file);
      } else {
        throw new Error("Nicht unterstütztes Format. Bitte ZIP (Apple Health) oder CSV hochladen.");
      }

      setResult(res);
      setStatus("success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import fehlgeschlagen");
      setStatus("error");
    }
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const onFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const reset = () => {
    setStatus("idle");
    setResult(null);
    setError("");
    if (fileRef.current) fileRef.current.value = "";
  };

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
      <h3 className="text-sm font-medium text-zinc-300 mb-3 flex items-center gap-2">
        <Upload className="h-4 w-4" />
        Health-Daten importieren
      </h3>

      {status === "idle" || status === "error" ? (
        <div
          onDrop={onDrop}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onClick={() => fileRef.current?.click()}
          className={`
            flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-6 cursor-pointer transition-colors
            ${dragOver ? "border-indigo-500 bg-indigo-500/10" : "border-zinc-700 hover:border-zinc-500 hover:bg-zinc-800/50"}
          `}
        >
          <FileUp className="h-8 w-8 text-zinc-500" />
          <p className="text-sm text-zinc-400 text-center">
            Apple Health Export (.zip) oder CSV hierher ziehen
          </p>
          <p className="text-xs text-zinc-600">
            Unterstützt: Apple Health ZIP, CSV (wide/long format)
          </p>
          <input
            ref={fileRef}
            type="file"
            accept=".zip,.csv"
            onChange={onFileSelect}
            className="hidden"
          />
        </div>
      ) : status === "uploading" ? (
        <div className="flex items-center justify-center gap-3 rounded-lg border border-zinc-700 p-6">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
          <span className="text-sm text-zinc-300">Importiere Daten...</span>
        </div>
      ) : status === "success" && result ? (
        <div className="space-y-2">
          <div className="flex items-start gap-2 rounded-lg border border-green-800/50 bg-green-900/20 p-3">
            <Check className="h-5 w-5 text-green-400 mt-0.5 shrink-0" />
            <div className="text-sm">
              <p className="text-green-300 font-medium">
                {result.days_imported} Tage importiert
              </p>
              <p className="text-zinc-400">
                {result.total_days_in_file} Tage in Datei gefunden
              </p>
              {result.kr_updates.length > 0 && (
                <p className="text-indigo-300 mt-1">
                  {result.kr_updates.length} Key Results aktualisiert
                </p>
              )}
            </div>
          </div>
          <button
            onClick={reset}
            className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            Weiteren Import starten
          </button>
        </div>
      ) : null}

      {status === "error" && error && (
        <div className="mt-2 flex items-start gap-2 rounded-lg border border-red-800/50 bg-red-900/20 p-3">
          <AlertCircle className="h-4 w-4 text-red-400 mt-0.5 shrink-0" />
          <div className="flex-1 text-sm text-red-300">{error}</div>
          <button onClick={reset} className="text-red-400 hover:text-red-300">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}
