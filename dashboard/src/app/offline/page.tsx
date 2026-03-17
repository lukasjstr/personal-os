export default function OfflinePage() {
  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center px-4">
      <div className="text-center max-w-md">
        <div className="text-6xl mb-6">📡</div>
        <h1 className="text-2xl font-bold text-white mb-3">Offline</h1>
        <p className="text-zinc-400 mb-6">
          Du bist gerade offline. Bitte prüfe deine Internetverbindung und versuche es erneut.
        </p>
        <a
          href="/"
          className="inline-block px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium transition-colors"
        >
          Erneut versuchen
        </a>
      </div>
    </div>
  );
}
