import { cn } from "@/lib/utils";

export default function LoadingSpinner({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center justify-center py-12", className)}>
      <div className="w-8 h-8 border-2 border-zinc-700 border-t-blue-500 rounded-full animate-spin" />
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const handleRetry = onRetry ?? (() => window.location.reload());
  return (
    <div className="flex items-center justify-center py-12 text-center">
      <div>
        <div className="text-3xl mb-2">⚠️</div>
        <div className="text-red-400 text-sm mb-3">{message}</div>
        <button
          onClick={handleRetry}
          className="text-xs text-zinc-400 hover:text-white border border-zinc-700 hover:border-zinc-500 px-3 py-1.5 rounded-lg transition-colors"
        >
          Erneut versuchen
        </button>
      </div>
    </div>
  );
}

export function EmptyState({ emoji, message }: { emoji: string; message: string }) {
  return (
    <div className="flex items-center justify-center py-12 text-center">
      <div>
        <div className="text-4xl mb-3">{emoji}</div>
        <div className="text-zinc-500 text-sm">{message}</div>
      </div>
    </div>
  );
}
