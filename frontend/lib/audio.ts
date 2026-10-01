/**
 * Browser audio helpers: push-to-talk recording (MediaRecorder), live captions via the
 * Web Speech API as a transcription fallback, and interviewer speech via speechSynthesis.
 */

export const MAX_RECORDING_MS = 120_000;

const MIME_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/ogg;codecs=opus",
  "audio/mp4",
];

export interface Recording {
  blob: Blob;
  durationSeconds: number;
}

function pickMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  return MIME_CANDIDATES.find((type) => MediaRecorder.isTypeSupported(type));
}

/** Records the microphone while a button/key is held. Reuses one mic stream. */
export class PushToTalkRecorder {
  private stream: MediaStream | null = null;
  private recorder: MediaRecorder | null = null;
  private chunks: Blob[] = [];
  private startedAt = 0;
  private autoStopTimer: ReturnType<typeof setTimeout> | null = null;
  private audioContext: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private levelBuffer: Uint8Array<ArrayBuffer> | null = null;

  static isSupported(): boolean {
    return (
      typeof window !== "undefined" &&
      typeof MediaRecorder !== "undefined" &&
      !!navigator.mediaDevices?.getUserMedia
    );
  }

  get isRecording(): boolean {
    return this.recorder?.state === "recording";
  }

  private async ensureStream(): Promise<MediaStream> {
    if (this.stream && this.stream.active) return this.stream;
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true },
    });
    this.audioContext = new AudioContext();
    const source = this.audioContext.createMediaStreamSource(this.stream);
    this.analyser = this.audioContext.createAnalyser();
    this.analyser.fftSize = 512;
    this.levelBuffer = new Uint8Array(this.analyser.fftSize);
    source.connect(this.analyser);
    return this.stream;
  }

  /** Start recording; `onAutoStop` fires if the two-minute limit is reached. */
  async start(onAutoStop: () => void): Promise<void> {
    if (this.isRecording) return;
    const stream = await this.ensureStream();
    if (this.audioContext?.state === "suspended") await this.audioContext.resume();
    const mimeType = pickMimeType();
    this.recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    this.chunks = [];
    this.recorder.ondataavailable = (event) => {
      if (event.data.size > 0) this.chunks.push(event.data);
    };
    this.recorder.start(250);
    this.startedAt = performance.now();
    this.autoStopTimer = setTimeout(onAutoStop, MAX_RECORDING_MS);
  }

  /** Stop recording and return the audio, or null if nothing was captured. */
  stop(): Promise<Recording | null> {
    if (this.autoStopTimer) clearTimeout(this.autoStopTimer);
    const recorder = this.recorder;
    if (!recorder || recorder.state === "inactive") return Promise.resolve(null);
    return new Promise((resolve) => {
      recorder.onstop = () => {
        const durationSeconds = (performance.now() - this.startedAt) / 1000;
        const blob = new Blob(this.chunks, { type: recorder.mimeType || "audio/webm" });
        resolve(blob.size > 0 ? { blob, durationSeconds } : null);
      };
      recorder.stop();
    });
  }

  /** Current input loudness in [0, 1], for visualisation. */
  level(): number {
    if (!this.analyser || !this.levelBuffer) return 0;
    this.analyser.getByteTimeDomainData(this.levelBuffer);
    let sum = 0;
    for (const sample of this.levelBuffer) {
      const centered = (sample - 128) / 128;
      sum += centered * centered;
    }
    return Math.min(1, Math.sqrt(sum / this.levelBuffer.length) * 4);
  }

  dispose(): void {
    if (this.autoStopTimer) clearTimeout(this.autoStopTimer);
    if (this.recorder && this.recorder.state !== "inactive") this.recorder.stop();
    this.stream?.getTracks().forEach((track) => track.stop());
    void this.audioContext?.close();
    this.stream = null;
    this.recorder = null;
    this.audioContext = null;
    this.analyser = null;
  }
}

// ----------------------------------------------------------- Web Speech API

interface SpeechRecognitionAlternativeLike {
  transcript: string;
}
interface SpeechRecognitionResultLike {
  isFinal: boolean;
  0: SpeechRecognitionAlternativeLike;
}
interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: ArrayLike<SpeechRecognitionResultLike>;
}
interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start(): void;
  stop(): void;
}
type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

function speechRecognitionClass(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

/**
 * Browser speech recognition, run alongside the recorder. Its transcript is used
 * when server-side transcription fails or the browser can't record audio.
 */
export class LiveCaptions {
  private recognition: SpeechRecognitionLike | null = null;
  private finalText = "";
  private interimText = "";
  private ended: Promise<void> = Promise.resolve();

  constructor(private readonly onUpdate?: (text: string) => void) {}

  static isSupported(): boolean {
    return speechRecognitionClass() !== null;
  }

  get text(): string {
    return `${this.finalText} ${this.interimText}`.replace(/\s+/g, " ").trim();
  }

  start(): void {
    const Recognition = speechRecognitionClass();
    if (!Recognition) return;
    this.finalText = "";
    this.interimText = "";
    const recognition = new Recognition();
    recognition.lang = "en-US";
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) this.finalText += ` ${result[0].transcript}`;
        else interim += result[0].transcript;
      }
      this.interimText = interim;
      this.onUpdate?.(this.text);
    };
    this.ended = new Promise((resolve) => {
      recognition.onend = () => resolve();
      recognition.onerror = () => resolve();
    });
    try {
      recognition.start();
      this.recognition = recognition;
    } catch {
      this.recognition = null;
    }
  }

  /** Stop listening and return the best transcript available within ~1.5s. */
  async stop(): Promise<string> {
    if (!this.recognition) return this.text;
    this.recognition.stop();
    this.recognition = null;
    await Promise.race([this.ended, new Promise((r) => setTimeout(r, 1500))]);
    return this.text;
  }
}

// ------------------------------------------------------------- text-to-speech

const PREFERRED_VOICE_HINTS: [RegExp, number][] = [
  [/natural/i, 6],
  [/google us english/i, 5],
  [/google uk english/i, 4],
  [/(aria|jenny|guy|samantha|daniel|serena|alex)/i, 3],
  [/(premium|enhanced)/i, 2],
];

export function pickVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  const english = voices.filter((voice) => voice.lang.toLowerCase().startsWith("en"));
  if (english.length === 0) return null;
  const score = (voice: SpeechSynthesisVoice) =>
    PREFERRED_VOICE_HINTS.reduce(
      (total, [hint, weight]) => total + (hint.test(voice.name) ? weight : 0),
      0,
    ) + (voice.lang.toLowerCase() === "en-us" ? 1 : 0);
  return [...english].sort((a, b) => score(b) - score(a))[0];
}

function loadVoices(): Promise<SpeechSynthesisVoice[]> {
  const synth = window.speechSynthesis;
  const voices = synth.getVoices();
  if (voices.length > 0) return Promise.resolve(voices);
  return new Promise((resolve) => {
    const done = () => resolve(synth.getVoices());
    synth.addEventListener("voiceschanged", done, { once: true });
    setTimeout(done, 1000);
  });
}

export function canSpeak(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

/** Split into sentences: Chrome cuts off single utterances longer than ~15 seconds. */
function sentences(text: string): string[] {
  return (
    text
      .match(/[^.!?]+[.!?]+["')\]]*\s*|[^.!?]+$/g)
      ?.map((s) => s.trim())
      .filter(Boolean) ?? [text]
  );
}

/** Speak `text`; resolves when finished or cancelled. Call `stopSpeaking` to skip. */
export async function speak(text: string): Promise<void> {
  if (!canSpeak()) return;
  const synth = window.speechSynthesis;
  synth.cancel();
  const voice = pickVoice(await loadVoices());
  for (const part of sentences(text)) {
    const finished = await new Promise<boolean>((resolve) => {
      const utterance = new SpeechSynthesisUtterance(part);
      if (voice) utterance.voice = voice;
      utterance.lang = voice?.lang ?? "en-US";
      utterance.rate = 1.03;
      // Some browsers never fire onend (no voices, blocked autoplay): don't hang the UI.
      const words = part.split(/\s+/).length;
      const watchdog = setTimeout(
        () => {
          synth.cancel();
          resolve(false);
        },
        4000 + words * 600,
      );
      utterance.onend = () => {
        clearTimeout(watchdog);
        resolve(true);
      };
      utterance.onerror = () => {
        clearTimeout(watchdog);
        resolve(false);
      };
      synth.speak(utterance);
    });
    if (!finished) return;
  }
}

export function stopSpeaking(): void {
  if (canSpeak()) window.speechSynthesis.cancel();
}
