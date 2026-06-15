/** VoiceCommand — floating-mic voice capture for free-form prompts.
 *
 *  Wires a state machine onto the browser's Web Speech API:
 *    idle → listening → confirming → idle (one-shot)
 *                  ↳ paused (extends silence timer to 20s)
 *                  ↳ closed (60s idle auto-close)
 *
 *  Recognised voice keywords (case-insensitive, last 3 spoken words):
 *    pause | wait | hold on    → silence timer extends to 20s
 *    go | proceed | continue   → resumes normal 5s silence timer
 *    run | go (in confirming)  → fires `voice-prompt` event
 *    cancel | quit (in confirming) → closes dialog
 *
 *  On "Run", emits a `voice-prompt` window event with the transcript;
 *  consumers (studio for Meshy, etc.) subscribe to that event.
 *
 *  Browser support: Chrome/Edge/Safari today via webkitSpeechRecognition;
 *  Firefox/Brave see a "Voice not supported — switch browsers" message.
 *  A server-side Whisper fallback is wired but stubbed at this phase.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { Mic, MicOff, Play, X, Loader2, Pause, Keyboard, History, Trash2 } from "lucide-react";
import { toast } from "sonner";

const SILENCE_MS_DEFAULT = 5000;
const SILENCE_MS_PAUSED = 20000;
const IDLE_MS_TOTAL = 60000;

const PAUSE_WORDS = ["pause", "wait", "hold on", "hold-on"];
const RESUME_WORDS = ["go", "proceed", "continue"];
const RUN_WORDS = ["run", "go"];
const CANCEL_WORDS = ["cancel", "quit"];

// Voice prompt history (localStorage-backed). Caps at 10 most-recent,
// de-duplicates on push so re-running an old favorite doesn't bloat
// the list.
const HISTORY_KEY = "lithoforge:voice-prompt-history";
const HISTORY_MAX = 10;

const loadHistory = () => {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.slice(0, HISTORY_MAX) : [];
  } catch {
    return [];
  }
};

const saveHistory = (items) => {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(items.slice(0, HISTORY_MAX)));
  } catch {
    /* quota / disabled storage — silently skip */
  }
};

const pushHistory = (prompt) => {
  const next = [
    prompt,
    ...loadHistory().filter((p) => p !== prompt),
  ].slice(0, HISTORY_MAX);
  saveHistory(next);
  return next;
};

const SR =
  typeof window !== "undefined"
    ? window.SpeechRecognition || window.webkitSpeechRecognition
    : null;
const IS_SUPPORTED = !!SR;

const tailMatches = (text, keywords) => {
  const tail = text.toLowerCase().trim().split(/\s+/).slice(-3).join(" ");
  return keywords.some((k) => tail.endsWith(k));
};

export default function VoiceCommand() {
  const [phase, setPhase] = useState("idle");
  const [transcript, setTranscript] = useState("");
  const [interim, setInterim] = useState("");
  const [continuous, setContinuous] = useState(false);
  const [history, setHistory] = useState(() => loadHistory());
  const [historyOpen, setHistoryOpen] = useState(false);

  const recognitionRef = useRef(null);
  const phaseRef = useRef("idle");
  useEffect(() => { phaseRef.current = phase; }, [phase]);
  const silenceTimerRef = useRef(null);
  const idleTimerRef = useRef(null);
  const silenceDurationRef = useRef(SILENCE_MS_DEFAULT);

  const stopRecognition = useCallback(() => {
    const r = recognitionRef.current;
    if (r) {
      try { r.onend = null; r.onresult = null; r.onerror = null; r.stop(); } catch { /* already stopped */ }
      recognitionRef.current = null;
    }
    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
    if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
  }, []);

  const close = useCallback(() => {
    stopRecognition();
    setPhase("idle");
    setTranscript("");
    setInterim("");
  }, [stopRecognition]);

  const armSilenceTimer = useCallback((ms) => {
    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
    silenceDurationRef.current = ms;
    silenceTimerRef.current = setTimeout(() => {
      // Move into the confirm dialog after pause-of-silence; STT is
      // stopped while user reviews so we don't mistake "run" inside
      // a re-opened mic for the confirm gesture.
      setPhase((current) => {
        if (current !== "listening" && current !== "paused") return current;
        const r = recognitionRef.current;
        if (r) {
          try { r.onend = null; r.stop(); } catch { /* already stopped */ }
        }
        return "confirming";
      });
    }, ms);
  }, []);

  const armIdleTimer = useCallback(() => {
    if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
    idleTimerRef.current = setTimeout(() => {
      toast("Voice input timed out", { description: "No response for 60 seconds." });
      close();
    }, IDLE_MS_TOTAL);
  }, [close]);

  const runCommand = useCallback(
    (text) => {
      const finalPrompt = (text ?? transcript).trim();
      if (!finalPrompt) {
        toast("Empty prompt — nothing to run.");
        return;
      }
      window.dispatchEvent(
        new CustomEvent("voice-prompt", { detail: { prompt: finalPrompt } }),
      );
      setHistory(pushHistory(finalPrompt));
      toast.success("Voice prompt sent", { description: finalPrompt });
      if (continuous) {
        setTranscript("");
        setInterim("");
        setPhase("listening");
        startRecognition();
      } else {
        close();
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [transcript, continuous, close],
  );

  const replayHistory = useCallback((prompt) => {
    window.dispatchEvent(
      new CustomEvent("voice-prompt", { detail: { prompt } }),
    );
    setHistory(pushHistory(prompt));
    setHistoryOpen(false);
    toast.success("Re-running prompt", { description: prompt });
  }, []);

  const clearHistory = useCallback(() => {
    saveHistory([]);
    setHistory([]);
    setHistoryOpen(false);
    toast("Voice prompt history cleared");
  }, []);

  const startRecognition = useCallback(() => {
    if (!IS_SUPPORTED) {
      toast.error("Voice not supported", {
        description: "Use Chrome, Edge, or Safari for voice commands.",
      });
      return;
    }
    const r = new SR();
    r.lang = "en-US";
    r.continuous = true;
    r.interimResults = true;
    recognitionRef.current = r;

    r.onresult = (ev) => {
      let added = "";
      let live = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const chunk = ev.results[i][0].transcript;
        if (ev.results[i].isFinal) added += chunk + " ";
        else live += chunk;
      }
      // Check the most-recent words for keyword triggers BEFORE
      // appending them to the transcript so we don't end up with
      // "pause" or "run" sitting inside the prompt.
      const probe = (added + live).toLowerCase();
      if (added && tailMatches(added, PAUSE_WORDS)) {
        setPhase("paused");
        armSilenceTimer(SILENCE_MS_PAUSED);
        armIdleTimer();
        return;
      }
      if (added && tailMatches(added, RESUME_WORDS)) {
        setPhase("listening");
        armSilenceTimer(SILENCE_MS_DEFAULT);
        armIdleTimer();
        return;
      }
      if (added) {
        setTranscript((prev) => (prev + " " + added).replace(/\s+/g, " ").trim());
      }
      setInterim(live);
      if (added || probe) {
        armSilenceTimer(silenceDurationRef.current);
        armIdleTimer();
      }
    };

    r.onerror = (ev) => {
      if (ev.error === "no-speech" || ev.error === "aborted") return;
      if (ev.error === "not-allowed") {
        toast.error("Microphone blocked", {
          description:
            "Click the 🔒 padlock in your address bar → Permissions → set Microphone to Allow, then click the mic again.",
          duration: 8000,
        });
      } else if (ev.error === "service-not-allowed") {
        toast.error("Voice service blocked", {
          description: "Browser or system has disabled speech recognition for this site.",
          duration: 6000,
        });
      } else {
        toast.error(`Voice error: ${ev.error}`);
      }
      close();
    };

    r.onend = () => {
      // Auto-restart while we're still in listening/paused — Chrome
      // cuts the session every ~60s otherwise.
      if (phase === "listening" || phase === "paused") {
        try { r.start(); } catch { /* already restarted */ }
      }
    };

    try { r.start(); } catch { /* already running */ }
  }, [armSilenceTimer, armIdleTimer, close, phase]);

  /** Pre-flight the mic with getUserMedia so we can surface the REAL
   *  block reason — the Web Speech API collapses everything into a
   *  generic "not-allowed". Returns true when the mic is usable. */
  const preflightMic = useCallback(async () => {
    if (window.self !== window.top) {
      toast.error("Mic blocked by embedding", {
        description:
          "This page is running inside an iframe which blocks microphone access. Open the app in its own browser tab.",
        duration: 9000,
      });
      return false;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      toast.error("Microphone unavailable", {
        description: "This browser does not expose microphone access on this page.",
      });
      return false;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((t) => t.stop());
      return true;
    } catch (err) {
      const msg = (err?.message || "").toLowerCase();
      if (err?.name === "NotAllowedError" && msg.includes("system")) {
        toast.error("Blocked by operating system", {
          description:
            "Your OS is blocking the microphone for this browser. Windows: Settings → Privacy & security → Microphone → turn ON 'Microphone access' AND 'Let desktop apps access your microphone'. macOS: System Settings → Privacy & Security → Microphone → enable your browser, then restart it.",
          duration: 12000,
        });
      } else if (err?.name === "NotAllowedError") {
        toast.error("Microphone blocked by browser", {
          description:
            "Click the 🔒 padlock in your address bar → Site settings → set Microphone to Allow, then reload the page.",
          duration: 9000,
        });
      } else if (err?.name === "NotFoundError" || err?.name === "DevicesNotFoundError") {
        toast.error("No microphone found", {
          description: "No microphone device was detected. Plug one in or check your sound settings.",
          duration: 9000,
        });
      } else if (err?.name === "NotReadableError" || err?.name === "TrackStartError") {
        toast.error("Microphone busy", {
          description:
            "Another app (or antivirus webcam/mic protection) is holding the microphone. Close other apps using the mic and try again.",
          duration: 9000,
        });
      } else {
        toast.error(`Mic check failed: ${err?.name || "unknown"}`, {
          description: err?.message || "Unknown microphone error.",
          duration: 9000,
        });
      }
      return false;
    }
  }, []);

  const openMic = useCallback(async () => {
    if (phase !== "idle") return;
    setTranscript("");
    setInterim("");
    if (!IS_SUPPORTED) {
      toast("Voice not supported in this browser", {
        description: "Type your prompt below instead.",
      });
      setPhase("typing");
      armIdleTimer();
      return;
    }
    // Show the modal right away so the UI responds instantly while the
    // browser permission prompt (if any) is on screen.
    setPhase("requesting");
    armIdleTimer();
    const micOk = await Promise.race([
      preflightMic(),
      new Promise((resolve) =>
        setTimeout(() => {
          toast("Mic permission still pending", {
            description:
              "Type your prompt below instead — or grant microphone access and click the mic again.",
            duration: 8000,
          });
          resolve(false);
        }, 10000),
      ),
    ]);
    // User may have closed the dialog while we waited.
    if (phaseRef.current !== "requesting") return;
    if (!micOk) {
      // Fall back to typed input so the feature stays usable.
      setPhase("typing");
      armIdleTimer();
      return;
    }
    setPhase("listening");
    silenceDurationRef.current = SILENCE_MS_DEFAULT;
    armSilenceTimer(SILENCE_MS_DEFAULT);
    armIdleTimer();
    startRecognition();
  }, [phase, armSilenceTimer, armIdleTimer, startRecognition, preflightMic]);

  // While the dialog is open, listen for voice "run"/"cancel" from
  // the user. We restart STT briefly just for the confirm gesture.
  useEffect(() => {
    if (phase !== "confirming") return;
    if (!IS_SUPPORTED) return;
    const r = new SR();
    r.lang = "en-US";
    r.continuous = true;
    r.interimResults = false;
    r.onresult = (ev) => {
      const last = ev.results[ev.results.length - 1][0].transcript;
      if (tailMatches(last, RUN_WORDS)) {
        try { r.stop(); } catch { /* already stopped */ }
        runCommand(transcript);
      } else if (tailMatches(last, CANCEL_WORDS)) {
        try { r.stop(); } catch { /* already stopped */ }
        close();
      }
    };
    r.onerror = () => { /* ignore confirm-loop errors */ };
    try { r.start(); } catch { /* ignore */ }
    return () => {
      try { r.onresult = null; r.onerror = null; r.stop(); } catch { /* ignore */ }
    };
  }, [phase, transcript, runCommand, close]);

  useEffect(() => () => stopRecognition(), [stopRecognition]);

  return (
    <>
      <button
        onClick={openMic}
        title={IS_SUPPORTED ? "Voice command" : "Voice not supported — opens typed prompt"}
        data-testid="voice-mic-fab"
        className="fixed bottom-20 right-5 z-40 w-12 h-12 rounded-full bg-zinc-100 text-zinc-950 hover:bg-amber-200 shadow-lg flex items-center justify-center transition-colors"
      >
        {IS_SUPPORTED ? <Mic size={18} /> : <MicOff size={18} />}
      </button>

      {history.length > 0 && phase === "idle" && (
        <button
          onClick={() => setHistoryOpen((v) => !v)}
          title={`Voice history · ${history.length} prompt${history.length === 1 ? "" : "s"}`}
          data-testid="voice-history-btn"
          className="fixed bottom-20 right-20 z-40 h-12 px-3 rounded-full bg-zinc-900 border border-zinc-700 text-zinc-200 hover:bg-zinc-800 shadow-lg flex items-center gap-1.5 transition-colors font-mono text-[10px] uppercase tracking-[0.15em]"
        >
          <History size={14} />
          {history.length}
        </button>
      )}

      {historyOpen && history.length > 0 && (
        <div
          className="fixed bottom-36 right-5 z-40 w-80 max-h-[60vh] bg-zinc-900 border border-zinc-700 shadow-2xl overflow-hidden flex flex-col"
          data-testid="voice-history-popover"
        >
          <div className="px-4 py-2.5 border-b border-zinc-800 flex items-center justify-between">
            <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-zinc-300">
              Voice history · last {history.length}
            </div>
            <button
              onClick={clearHistory}
              title="Clear all"
              data-testid="voice-history-clear"
              className="text-zinc-500 hover:text-red-300"
            >
              <Trash2 size={14} />
            </button>
          </div>
          <div className="overflow-y-auto divide-y divide-zinc-800">
            {history.map((p, i) => (
              <button
                key={`${p}-${i}`}
                onClick={() => replayHistory(p)}
                data-testid={`voice-history-item-${i}`}
                className="w-full text-left px-4 py-3 hover:bg-zinc-800 group flex items-start gap-2"
                title={p}
              >
                <Play size={12} className="text-emerald-400 mt-0.5 opacity-60 group-hover:opacity-100 flex-shrink-0" />
                <span className="font-mono text-xs text-zinc-200 line-clamp-3 leading-snug">
                  {p}
                </span>
              </button>
            ))}
          </div>
          <button
            onClick={() => setHistoryOpen(false)}
            data-testid="voice-history-close"
            className="px-4 py-2 border-t border-zinc-800 font-mono text-[10px] uppercase tracking-[0.18em] text-zinc-500 hover:text-zinc-100 hover:bg-zinc-800"
          >
            Close
          </button>
        </div>
      )}

      {phase !== "idle" && (
        <div
          className="fixed inset-0 z-50 bg-zinc-950/70 backdrop-blur-sm flex items-center justify-center px-4"
          data-testid="voice-modal"
        >
          <div className="w-full max-w-xl bg-zinc-900 border border-zinc-800 p-6 space-y-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {phase === "typing" ? (
                  <Keyboard size={20} className="text-amber-400" data-testid="voice-typing-icon" />
                ) : phase === "confirming" ? (
                  <Mic size={20} className="text-amber-400" data-testid="voice-confirm-icon" />
                ) : phase === "paused" ? (
                  <Pause size={20} className="text-amber-300" data-testid="voice-paused-icon" />
                ) : (
                  <Mic size={20} className="text-emerald-400 animate-pulse" data-testid="voice-listening-icon" />
                )}
                <div className="font-display font-bold text-lg">
                  {phase === "typing" ? "Type your prompt" :
                   phase === "confirming" ? "Confirm prompt" :
                   phase === "paused" ? "Listening (paused, 20s window)" :
                   phase === "requesting" ? "Requesting microphone…" : "Listening…"}
                </div>
              </div>
              <button
                onClick={close}
                title="Close"
                data-testid="voice-close"
                className="text-zinc-500 hover:text-zinc-100"
              >
                <X size={18} />
              </button>
            </div>

            {phase === "typing" || phase === "confirming" ? (
              <textarea
                value={transcript}
                onChange={(e) => setTranscript(e.target.value)}
                placeholder={phase === "typing" ? "Describe what to generate, e.g. 'a lighthouse on a rocky cliff at sunset'" : ""}
                autoFocus
                rows={4}
                data-testid="voice-typed-input"
                className="w-full bg-zinc-950 border border-zinc-800 p-4 min-h-[100px] font-mono text-sm text-zinc-100 resize-y focus:outline-none focus:border-amber-400/60 placeholder:text-zinc-600"
              />
            ) : (
              <div
                className="bg-zinc-950 border border-zinc-800 p-4 min-h-[100px] font-mono text-sm text-zinc-100 whitespace-pre-wrap"
                data-testid="voice-transcript"
              >
                {transcript || <span className="text-zinc-600">Start speaking…</span>}
                {interim && <span className="text-zinc-500"> {interim}</span>}
              </div>
            )}

            {phase === "confirming" || phase === "typing" ? (
              <div className="flex items-center gap-3">
                <button
                  onClick={() => runCommand(transcript)}
                  data-testid="voice-run"
                  className="flex-1 h-11 bg-emerald-500 hover:bg-emerald-400 text-zinc-950 font-mono text-xs uppercase tracking-[0.18em] font-bold flex items-center justify-center gap-2"
                >
                  <Play size={14} /> Run
                </button>
                <button
                  onClick={close}
                  data-testid="voice-cancel"
                  className="flex-1 h-11 bg-zinc-800 hover:bg-zinc-700 text-zinc-100 font-mono text-xs uppercase tracking-[0.18em] font-bold"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-[0.18em] text-zinc-500">
                <span className="flex items-center gap-2">
                  <Loader2 size={12} className="animate-spin" />
                  {phase === "requesting"
                    ? "Waiting for browser microphone permission…"
                    : 'Say "pause" to extend, "run" to confirm, "cancel" to quit'}
                </span>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={continuous}
                    onChange={(e) => setContinuous(e.target.checked)}
                    data-testid="voice-continuous"
                    className="accent-amber-400"
                  />
                  Continuous mode
                </label>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
