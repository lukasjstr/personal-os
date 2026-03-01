interface Props {
  level: number;
  levelTitle: string;
  totalXp: number;
  xpProgress: number;
  xpToNext: number;
  compact?: boolean;
}

export default function XPBar({
  level,
  levelTitle,
  totalXp,
  xpProgress,
  xpToNext,
  compact = false,
}: Props) {
  const pct = xpToNext > 0 ? Math.min(100, Math.round((xpProgress / xpToNext) * 100)) : 100;

  if (compact) {
    return (
      <div className="px-3 py-2">
        <div className="flex items-center gap-2 mb-1">
          <div className="w-6 h-6 rounded bg-gradient-to-br from-yellow-500 to-orange-600 flex items-center justify-center shrink-0">
            <span className="text-white font-bold text-xs">{level}</span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-0.5">
              <span className="text-zinc-400 text-xs truncate">{levelTitle}</span>
              <span className="text-zinc-600 text-xs">{pct}%</span>
            </div>
            <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-yellow-500 to-orange-500 rounded-full"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-yellow-500 to-orange-600 flex items-center justify-center shrink-0">
          <span className="text-white font-bold text-xl">{level}</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-2">
              <span className="text-white font-semibold text-sm">Level {level}</span>
              <span className="text-zinc-400 text-xs bg-zinc-800 px-2 py-0.5 rounded-full">
                {levelTitle}
              </span>
            </div>
            <span className="text-zinc-500 text-xs">
              {xpProgress.toLocaleString()} / {xpToNext.toLocaleString()} XP
            </span>
          </div>
          <div className="w-full h-3 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-yellow-500 to-orange-500 rounded-full transition-all duration-700"
              style={{ width: `${pct}%` }}
            />
          </div>
          <div className="text-zinc-600 text-xs mt-1">{totalXp.toLocaleString()} XP gesamt</div>
        </div>
      </div>
    </div>
  );
}
