"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Send, X, Check, Pencil, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import type { GoalPlan } from "@/lib/api";

interface ChatMessage {
  role: "bot" | "user";
  text: string;
  buttons?: { text: string; action: string }[];
  plan?: GoalPlan;
}

export default function GoalCoachPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string>("idle"); // idle, in_progress, plan_review, completed
  const [goalStarted, setGoalStarted] = useState(false);
  const [done, setDone] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
  }, []);

  useEffect(() => { scrollToBottom(); }, [messages, scrollToBottom]);

  const addBotMessage = (text: string, buttons?: ChatMessage["buttons"], plan?: GoalPlan) => {
    setMessages((prev) => [...prev, { role: "bot", text, buttons, plan }]);
  };

  const addUserMessage = (text: string) => {
    setMessages((prev) => [...prev, { role: "user", text }]);
  };

  // Start onboarding
  const handleStart = async () => {
    if (!input.trim() || loading) return;
    const goal = input.trim();
    setInput("");
    addUserMessage(goal);
    setLoading(true);
    setGoalStarted(true);

    try {
      const res = await api.goalOnboardingStart(goal);
      setStatus(res.status);
      addBotMessage(res.message);
    } catch (err) {
      addBotMessage("Fehler beim Starten. Bitte versuche es erneut.");
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  // Answer a question
  const handleAnswer = async () => {
    if (!input.trim() || loading) return;
    const text = input.trim();
    setInput("");
    addUserMessage(text);
    setLoading(true);

    try {
      const res = await api.goalOnboardingAnswer(text);
      setStatus(res.status);

      if (res.status === "plan_review" && res.draft_payload) {
        addBotMessage(res.message, [
          { text: "Erstellen", action: "confirm" },
          { text: "Anpassen", action: "adjust" },
          { text: "Verwerfen", action: "cancel" },
        ], res.draft_payload);
      } else {
        addBotMessage(res.message);
      }
    } catch (err) {
      addBotMessage("Fehler bei der Verarbeitung. Bitte versuche es erneut.");
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  // Handle button actions
  const handleAction = async (action: string) => {
    if (loading) return;
    setLoading(true);

    try {
      if (action === "confirm") {
        addUserMessage("Erstellen");
        const res = await api.goalOnboardingConfirm();
        setStatus(res.status);
        addBotMessage(res.message);
        if (res.status === "completed") setDone(true);
      } else if (action === "adjust") {
        addUserMessage("Anpassen");
        const res = await api.goalOnboardingAdjust();
        setStatus(res.status);
        addBotMessage(res.message);
      } else if (action === "cancel") {
        addUserMessage("Verwerfen");
        await api.goalOnboardingCancel();
        setStatus("idle");
        addBotMessage("Onboarding abgebrochen. Du kannst jederzeit ein neues Ziel starten.");
        setGoalStarted(false);
      }
    } catch (err) {
      addBotMessage("Fehler. Bitte versuche es erneut.");
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleSubmit = () => {
    if (!goalStarted) {
      handleStart();
    } else if (status === "in_progress" || status === "plan_review") {
      handleAnswer();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-2rem)] max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
        <div className="flex items-center gap-3">
          <span className="text-2xl">🎯</span>
          <div>
            <h1 className="text-white font-semibold text-sm">Ziel-Coaching</h1>
            <p className="text-zinc-500 text-xs">Dein AI Coach hilft dir beim Planen</p>
          </div>
        </div>
        <button
          onClick={() => router.push("/objectives")}
          className="text-zinc-500 hover:text-zinc-300 transition-colors"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {/* Initial prompt */}
        {messages.length === 0 && (
          <div className="text-center py-12">
            <div className="text-5xl mb-4">🤖</div>
            <h2 className="text-xl font-bold text-white mb-2">Was willst du erreichen?</h2>
            <p className="text-zinc-400 text-sm max-w-md mx-auto">
              Beschreib dein Ziel — ich stelle dir ein paar Fragen und erstelle dann einen kompletten Plan mit Tasks, Routinen, und Erinnerungen.
            </p>
            <div className="flex flex-wrap justify-center gap-2 mt-6">
              {["Gesünder leben", "Mehr Sport machen", "Spanisch lernen", "Business aufbauen", "Mehr lesen"].map((example) => (
                <button
                  key={example}
                  onClick={() => setInput(example)}
                  className="px-3 py-1.5 bg-zinc-800 border border-zinc-700 rounded-full text-zinc-400 text-sm hover:text-white hover:border-zinc-500 transition-colors"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Messages */}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] ${msg.role === "user" ? "order-1" : ""}`}>
              {msg.role === "bot" && (
                <div className="flex items-start gap-2">
                  <span className="text-lg mt-0.5 shrink-0">🤖</span>
                  <div className="space-y-3">
                    <div className="bg-zinc-800 rounded-2xl rounded-tl-sm px-4 py-3 text-zinc-200 text-sm whitespace-pre-wrap leading-relaxed">
                      {msg.text}
                    </div>

                    {/* Plan preview */}
                    {msg.plan && <PlanPreview plan={msg.plan} />}

                    {/* Action buttons */}
                    {msg.buttons && (
                      <div className="flex gap-2 flex-wrap">
                        {msg.buttons.map((btn) => (
                          <button
                            key={btn.action}
                            onClick={() => handleAction(btn.action)}
                            disabled={loading}
                            className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors disabled:opacity-50 ${
                              btn.action === "confirm"
                                ? "bg-green-600 hover:bg-green-500 text-white"
                                : btn.action === "cancel"
                                ? "bg-zinc-700 hover:bg-zinc-600 text-zinc-300"
                                : "bg-blue-600 hover:bg-blue-500 text-white"
                            }`}
                          >
                            {btn.action === "confirm" && <Check className="inline h-3.5 w-3.5 mr-1.5" />}
                            {btn.action === "adjust" && <Pencil className="inline h-3.5 w-3.5 mr-1.5" />}
                            {btn.action === "cancel" && <X className="inline h-3.5 w-3.5 mr-1.5" />}
                            {btn.text}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {msg.role === "user" && (
                <div className="bg-blue-600 rounded-2xl rounded-tr-sm px-4 py-3 text-white text-sm">
                  {msg.text}
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Loading indicator */}
        {loading && (
          <div className="flex items-start gap-2">
            <span className="text-lg mt-0.5">🤖</span>
            <div className="bg-zinc-800 rounded-2xl rounded-tl-sm px-4 py-3">
              <Loader2 className="h-4 w-4 text-zinc-400 animate-spin" />
            </div>
          </div>
        )}

        {/* Done */}
        {done && (
          <div className="text-center py-6">
            <div className="text-5xl mb-3 animate-bounce">🚀</div>
            <p className="text-white font-bold text-lg mb-2">Ziel aktiviert!</p>
            <div className="flex gap-3 justify-center">
              <button
                onClick={() => router.push("/objectives")}
                className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-sm font-medium transition-colors"
              >
                Ziele ansehen
              </button>
              <button
                onClick={() => { setMessages([]); setGoalStarted(false); setDone(false); setStatus("idle"); }}
                className="px-5 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl text-sm transition-colors"
              >
                Weiteres Ziel
              </button>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      {!done && (
        <div className="px-4 py-3 border-t border-zinc-800">
          <div className="flex gap-2">
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={!goalStarted ? "Dein Ziel eingeben..." : "Deine Antwort..."}
              disabled={loading}
              autoFocus
              className="flex-1 bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm placeholder:text-zinc-500 focus:outline-none focus:border-blue-500 disabled:opacity-50"
            />
            <button
              onClick={handleSubmit}
              disabled={!input.trim() || loading}
              className="px-4 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl transition-colors disabled:opacity-40"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function PlanPreview({ plan }: { plan: GoalPlan }) {
  const obj = plan.objective;
  return (
    <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-xl">{obj.emoji || "🎯"}</span>
        <div>
          <div className="text-white font-semibold text-sm">{obj.title}</div>
          <div className="text-zinc-500 text-xs">{obj.category} · bis {obj.target_date}</div>
        </div>
      </div>

      {plan.key_results?.length > 0 && (
        <div>
          <div className="text-zinc-400 text-xs font-semibold mb-1.5">Key Results</div>
          {(plan.key_results as { title: string }[]).map((kr, i) => (
            <div key={i} className="text-zinc-300 text-xs flex items-start gap-1.5 py-0.5">
              <span className="text-blue-400 shrink-0">•</span>
              {kr.title}
            </div>
          ))}
        </div>
      )}

      {plan.tasks?.length > 0 && (
        <div>
          <div className="text-zinc-400 text-xs font-semibold mb-1.5">Tasks ({plan.tasks.length})</div>
          {plan.tasks.slice(0, 5).map((t, i) => (
            <div key={i} className="text-zinc-300 text-xs flex items-start gap-1.5 py-0.5">
              <span className="text-green-400 shrink-0">☐</span>
              {t.title}
            </div>
          ))}
          {plan.tasks.length > 5 && (
            <div className="text-zinc-500 text-xs italic">+{plan.tasks.length - 5} weitere</div>
          )}
        </div>
      )}

      {plan.routines?.length > 0 && (
        <div>
          <div className="text-zinc-400 text-xs font-semibold mb-1">Routinen</div>
          {plan.routines.map((r, i) => (
            <div key={i} className="text-zinc-300 text-xs py-0.5">
              🔁 {r.title} ({r.frequency})
            </div>
          ))}
        </div>
      )}

      {plan.first_step && (
        <div className="bg-green-950/30 border border-green-800/30 rounded-lg px-3 py-2">
          <div className="text-green-400 text-xs font-semibold">Erster Schritt heute</div>
          <div className="text-green-200 text-xs">{plan.first_step}</div>
        </div>
      )}
    </div>
  );
}
