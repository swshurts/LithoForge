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
import { Mic, MicOff, Play, X, Loader2, Pause } from "lucide-react";
import { toast } from "sonner";

const SILENCE_MS_DEFAULT = 5000;
const SILENCE_MS_PAUSED = 20000;
const IDLE_MS_TOTAL = 60000;

const PAUSE_WORDS = ["pause", "wait", "hold on", "hold-on"];
const RESUME_WORDS = ["go", "proceed", "continue"];
const RUN_WORDS = ["run", "go"];
const CANCEL_WORDS = ["cancel", "quit"];

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

  const recognitionRef = useRef(null);
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
      toast.error(`Voice error: ${ev.error}`);
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

  const openMic = useCallback(() => {
    if (phase !== "idle") return;
    setTranscript("");
    setInterim("");
    setPhase("listening");
    silenceDurationRef.current = SILENCE_MS_DEFAULT;
    armSilenceTimer(SILENCE_MS_DEFAULT);
    armIdleTimer();
    startRecognition();
  }, [phase, armSilenceTimer, armIdleTimer, startRecognition]);

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
        disabled={!IS_SUPPORTED}
        title={IS_SUPPORTED ? "Voice command" : "Voice not supported in this browser"}
        data-testid="voice-mic-fab"
        className="fixed bottom-5 right-5 z-40 w-12 h-12 rounded-full bg-zinc-100 text-zinc-950 hover:bg-amber-200 disabled:opacity-40 disabled:cursor-not-allowed shadow-lg flex items-center justify-center transition-colors"
      >
        {IS_SUPPORTED ? <Mic size={18} /> : <MicOff size={18} />}
      </button>

      {phase !== "idle" && (
        <div
          className="fixed inset-0 z-50 bg-zinc-950/70 backdrop-blur-sm flex items-center justify-center px-4"
          data-testid="voice-modal"
        >
          <div className="w-full max-w-xl bg-zinc-900 border border-zinc-800 p-6 space-y-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {phase === "confirming" ? (
                  <Mic size={20} className="text-amber-400" data-testid="voice-confirm-icon" />
                ) : phase === "paused" ? (
                  <Pause size={20} className="text-amber-300" data-testid="voice-paused-icon" />
                ) : (
                  <Mic size={20} className="text-emerald-400 animate-pulse" data-testid="voice-listening-icon" />
                )}
                <div className="font-display font-bold text-lg">
                  {phase === "confirming" ? "Confirm prompt" :
                   phase === "paused" ? "Listening (paused, 20s window)" : "Listening…"}
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

            <div
              className="bg-zinc-950 border border-zinc-800 p-4 min-h-[100px] font-mono text-sm text-zinc-100 whitespace-pre-wrap"
              data-testid="voice-transcript"
            >
              {transcript || <span className="text-zinc-600">Start speaking…</span>}
              {interim && <span className="text-zinc-500"> {interim}</span>}
            </div>

            {phase === "confirming" ? (
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
                  Say &quot;pause&quot; to extend, &quot;run&quot; to confirm, &quot;cancel&quot; to quit
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
