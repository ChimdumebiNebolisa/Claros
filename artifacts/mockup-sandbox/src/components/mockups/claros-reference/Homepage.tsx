import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  ArrowDown,
  ArrowRight,
  Check,
  ChevronDown,
  FileText,
  Menu,
  Mic,
  MicOff,
  Send,
  ShieldCheck,
  X,
} from "lucide-react";
import { DEMO_QUESTIONS, type DemoQuestionId } from "../../../lib/claros-demo-contract";
import { useRealtimeDemo } from "./_useRealtimeDemo";

const orbitSymbols = [
  { glyph: "x²", kind: "math", pos: "symbol-1" },
  { glyph: "π", kind: "math", pos: "symbol-2" },
  { glyph: "√", kind: "math", pos: "symbol-3" },
  { glyph: "¾", kind: "fraction", pos: "symbol-4" },
  { glyph: "÷", kind: "math", pos: "symbol-5" },
  { glyph: "Aa", kind: "letters", pos: "symbol-6" },
  { glyph: "“ ”", kind: "quote", pos: "symbol-7" },
  { glyph: "¶", kind: "letters", pos: "symbol-8" },
  { glyph: "?", kind: "punct", pos: "symbol-9" },
  { glyph: "∑", kind: "math", pos: "symbol-10" },
  { glyph: "½", kind: "fraction", pos: "symbol-11" },
  { glyph: "…", kind: "punct", pos: "symbol-12" },
  { glyph: "∠", kind: "math", pos: "symbol-13" },
  { glyph: "!", kind: "punct", pos: "symbol-14" },
  { glyph: "≠", kind: "math", pos: "symbol-15" },
  { glyph: "()", kind: "letters", pos: "symbol-16" },
  { glyph: "∴", kind: "math", pos: "symbol-17" },
  { glyph: ":", kind: "punct", pos: "symbol-18" },
];
const waveformFactors = [0.4, 0.7, 0.52, 1, 0.64, 0.82, 0.45, 0.94, 0.58, 0.76, 0.38, 0.9, 0.62, 0.48, 0.8, 0.55, 0.98, 0.43, 0.72, 0.5, 0.88, 0.6, 0.4, 0.78, 0.53, 0.95, 0.63, 0.45, 0.82, 0.56, 0.73, 0.42, 0.9, 0.61];

function BrandMark() {
  return (
    <svg className="cl-mark" viewBox="0 0 28 28" aria-hidden="true">
      <path d="M7 0h14a7 7 0 0 1 7 7v14a7 7 0 0 1-7 7H2a2 2 0 0 1-2-2V7a7 7 0 0 1 7-7Z" fill="#155eef" />
      <path d="M286-9Q212-9 156.5 37T70.5 166.5T40 364Q40 474 73.5 556.5T163.5 684.5T289 730Q330 730 361 722.5T416 703Q428 696 428 682L431 530Q431 513 419 513Q408 513 405 526L395 563Q374 641 346.5 671T281 701Q211 701 164.5 614.5T118 364Q118 252 141.5 175T202.5 59T282 20Q327 20 354.5 48T401 156L413 205Q416 220 429 218Q440 216 440 201L436 39Q436 25 423 18Q399 6 366.5-1.5T286-9Z" fill="#fff" transform="translate(9.92 20.2) scale(.017 -.017)" />
    </svg>
  );
}

function AudioWave({ level, active }: { level: number; active: boolean }) {
  return (
    <div className={`cl-audio-wave ${active ? "has-audio" : ""}`} aria-hidden="true">
      {waveformFactors.map((factor, index) => {
        const liveHeight = active ? Math.max(3, 5 + level * factor * 43) : 3;
        return <i key={index} style={{ height: `${liveHeight}px` }} />;
      })}
    </div>
  );
}

export function Homepage() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<DemoQuestionId>("math");
  const [panelOpen, setPanelOpen] = useState(false);
  const [typedMessage, setTypedMessage] = useState("");
  const panelRef = useRef<HTMLElement>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  const demo = useRealtimeDemo(selectedId);
  const selectedQuestion = DEMO_QUESTIONS[selectedId];
  const lockedTopic = demo.active || demo.status === "connecting";
  const canSend = ["ready", "listening"].includes(demo.status) && !!typedMessage.trim();
  useEffect(() => {
    if (!panelOpen) return;
    const behavior = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
    panelRef.current?.scrollIntoView({ behavior, block: "center" });
    panelRef.current?.focus({ preventScroll: true });
  }, [panelOpen]);

  const scrollTo = (id: string) => {
    setMenuOpen(false);
    const behavior = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
    document.getElementById(id)?.scrollIntoView({ behavior, block: "start" });
  };

  const openWithVoice = () => {
    returnFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setPanelOpen(true);
    setTypedMessage("");
    void demo.startVoice();
  };

  const openWithText = () => {
    returnFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setPanelOpen(true);
    setTypedMessage("");
    void demo.startText();
  };

  const closeInteraction = () => {
    demo.endSession();
    setPanelOpen(false);
    setTypedMessage("");
    returnFocus.current?.focus();
  };

  const submitText = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (demo.sendMessage(typedMessage)) setTypedMessage("");
  };

  const startAgain = (mode: "voice" | "text") => {
    setTypedMessage("");
    if (mode === "voice") void demo.startVoice();
    else void demo.startText();
  };

  const elapsedLabel = `${Math.floor(demo.elapsed / 60)}:${String(demo.elapsed % 60).padStart(2, "0")}`;
  const currentStatus = ({
    idle: "Ready when you are",
    connecting: "Connecting to your conversation…",
    ready: "You can type a thought",
    listening: "Listening",
    thinking: "Thinking through that",
    speaking: "Claros is speaking",
    ended: "Conversation ended",
    error: "Couldn’t start the conversation",
  } as const)[demo.status];

  return (
    <div className="claros-home">
      <style>{`
        .claros-home {
          --cl-ink:#172d3b; --cl-muted:#617480; --cl-blue:#155eef; --cl-blue-dark:#104ac1;
          --cl-blue-wash:#eaf1ff; --cl-paper:#fafaf6; --cl-card:#fffefa; --cl-line:#dfe7e2;
          --cl-mint:#e8f1eb; --cl-lime:#d8e99b;
          min-height:100dvh; overflow:hidden; background:var(--cl-paper); color:var(--cl-ink);
          font-family:"DM Sans","Avenir Next",Avenir,ui-sans-serif,system-ui,sans-serif; -webkit-font-smoothing:antialiased;
        }
        .claros-home *{box-sizing:border-box}.claros-home button,.claros-home a,.claros-home input{font:inherit}
        .claros-home button{cursor:pointer}.claros-home a{color:inherit;text-decoration:none}
        .claros-home button:focus-visible,.claros-home a:focus-visible,.claros-home input:focus-visible{outline:3px solid #88b39c;outline-offset:3px}
        .cl-sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
        .cl-shell{width:min(1160px,calc(100% - 56px));margin:0 auto}
        .cl-header{height:78px;display:flex;align-items:center;justify-content:space-between;position:relative;z-index:20}
        .cl-brand{display:inline-flex;align-items:center;gap:10px;font-size:20px;font-weight:750;letter-spacing:-.045em}
        .cl-mark{width:28px;height:28px;flex:none;display:inline-block}
        .cl-nav{display:flex;align-items:center;gap:34px;color:#50636e;font-size:13px;font-weight:650}
        .cl-nav a:hover,.cl-footer-links a:hover{color:var(--cl-blue)}
        .cl-button{display:inline-flex;min-height:46px;align-items:center;justify-content:center;gap:10px;padding:0 20px;border:0;border-radius:999px;background:var(--cl-blue);color:white!important;font-size:13px;font-weight:750;transition:transform .18s ease,background .18s ease}
        .cl-button:hover{background:var(--cl-blue-dark);transform:translateY(-2px)}.cl-button svg{width:16px;height:16px}
        .cl-button:disabled,.cl-button-secondary:disabled{cursor:not-allowed;opacity:.55;transform:none}
        .cl-menu-toggle{display:none;width:46px;height:46px;align-items:center;justify-content:center;border:1px solid var(--cl-line);border-radius:50%;background:var(--cl-card);color:var(--cl-ink)}
        .cl-menu-panel{display:none}
        .cl-hero{height:625px;position:relative;isolation:isolate;display:grid;place-items:center;text-align:center}
        .cl-hero:before{content:"";position:absolute;z-index:-1;inset:-20px -10vw 0;background:radial-gradient(ellipse at 50% 45%,rgba(216,233,155,.33),rgba(232,241,235,.45) 34%,transparent 69%);pointer-events:none}
        .cl-hero:after{content:"";position:absolute;z-index:-1;width:min(880px,88vw);height:460px;left:50%;top:50%;transform:translate(-50%,-43%);border:1px solid rgba(21,94,239,.055);border-radius:50%;box-shadow:0 0 0 54px rgba(21,94,239,.022),0 0 0 108px rgba(21,94,239,.016);pointer-events:none}
        .cl-hero-core{position:relative;z-index:2;max-width:760px;padding:0 16px;margin-top:-12px}
        .cl-eyebrow{display:inline-flex;align-items:center;gap:9px;color:#315c78;font-size:10px;font-weight:800;letter-spacing:.145em;text-transform:uppercase}
        .cl-eyebrow-dot{width:7px;height:7px;border-radius:50%;background:#9bb943;box-shadow:0 0 0 4px rgba(155,185,67,.13)}
        .cl-hero h1{max-width:760px;margin:21px auto 0;font-size:clamp(54px,7.4vw,88px);line-height:.98;letter-spacing:-.075em;font-weight:690}
        .cl-hero h1 span{color:var(--cl-blue)}
        .cl-hero-copy{max-width:555px;margin:22px auto 0;color:var(--cl-muted);font-size:15px;line-height:1.75}
        .cl-hero-actions{display:flex;justify-content:center;margin-top:26px}
        .cl-hero-under{margin:13px 0 0;color:#82908b;font-size:10px}
        .cl-hero-down{position:absolute;z-index:3;bottom:28px;left:50%;transform:translateX(-50%);display:grid;place-items:center;width:36px;height:36px;border:1px solid #d9e2d8;border-radius:50%;background:rgba(255,254,250,.78);color:#687f75}
        .cl-hero-down svg{width:15px;height:15px}
        .cl-orbit-symbol{position:absolute;z-index:1;display:grid;place-items:center;min-width:44px;height:44px;padding:0 11px;border:1px solid rgba(215,224,217,.93);border-radius:14px;background:rgba(255,254,250,.88);box-shadow:0 10px 24px rgba(36,66,66,.075);color:#2d5771;font-family:Georgia,"Times New Roman",serif;font-size:20px;line-height:1;animation:cl-drift 7s ease-in-out infinite alternate;user-select:none}
        .cl-orbit-symbol.math{color:#155eef;background:#f7f9ff}.cl-orbit-symbol.fraction{color:#59764c;background:#f6f8e9}.cl-orbit-symbol.letters{font-family:ui-sans-serif,system-ui,sans-serif;font-size:16px;font-weight:700;color:#526e78}.cl-orbit-symbol.quote{font-size:17px;color:#826d8b}.cl-orbit-symbol.punct{font-size:23px;color:#9b704a}
        .symbol-1{left:8%;top:14%;transform:rotate(-11deg);animation-delay:-2s}.symbol-2{left:24%;top:4%;animation-delay:-4s}.symbol-3{left:43%;top:3%;transform:rotate(9deg);animation-delay:-1s}.symbol-4{right:23%;top:5%;animation-delay:-3s}.symbol-5{right:7%;top:17%;transform:rotate(8deg);animation-delay:-5s}
        .symbol-6{right:2%;top:41%;transform:rotate(-8deg);animation-delay:-2.5s}.symbol-7{right:9%;bottom:17%;transform:rotate(7deg);animation-delay:-1s}.symbol-8{right:27%;bottom:5%;animation-delay:-4s}.symbol-9{left:45%;bottom:3%;transform:rotate(-8deg);animation-delay:-3s}
        .symbol-10{left:25%;bottom:5%;transform:rotate(7deg);animation-delay:-5s}.symbol-11{left:8%;bottom:17%;animation-delay:-1.5s}.symbol-12{left:1%;top:43%;transform:rotate(9deg);animation-delay:-4s}
        .symbol-13{left:15%;top:32%;transform:rotate(-5deg);animation-delay:-2.8s}.symbol-14{right:14%;top:33%;animation-delay:-1.7s}.symbol-15{left:18%;bottom:35%;transform:rotate(8deg);animation-delay:-3.5s}
        .symbol-16{right:18%;bottom:34%;transform:rotate(-6deg);animation-delay:-2.2s}.symbol-17{left:36%;top:7%;animation-delay:-5s}.symbol-18{right:36%;top:7%;transform:rotate(9deg);animation-delay:-2s}
        @keyframes cl-drift{from{translate:0 0}to{translate:0 -7px}}
        .cl-try{padding:54px 0 84px;background:#edf4ef;border-top:1px solid #e3ebe5;border-bottom:1px solid #e3ebe5;scroll-margin-top:8px}
        .cl-try-inner{max-width:770px;margin:0 auto}
        .cl-try-kicker{color:#476976;text-align:center;text-transform:uppercase;letter-spacing:.16em;font-size:10px;font-weight:850}
        .cl-try h2{margin:10px 0 0;text-align:center;font-size:clamp(34px,4.5vw,48px);line-height:1.05;letter-spacing:-.065em}
        .cl-topic-row{display:flex;justify-content:center;gap:8px;margin:24px 0 13px}
        .cl-topic{min-height:38px;padding:0 15px;border:1px solid #d6e0d7;border-radius:999px;background:transparent;color:#5d726e;font-size:11px;font-weight:700}
        .cl-topic.selected{border-color:#9bb5a0;background:#fffefa;color:#22506a;box-shadow:0 3px 10px rgba(24,61,61,.06)}
        .cl-topic:disabled{cursor:not-allowed;opacity:.56}
        .cl-question{padding:20px 23px;border:1px solid #d9e4dc;border-radius:16px;background:#fffefa;box-shadow:0 8px 20px rgba(34,61,61,.04)}
        .cl-question-subject{display:flex;align-items:center;gap:7px;color:#728278;font-size:9px;font-weight:800;letter-spacing:.11em;text-transform:uppercase}
        .cl-question-subject svg{width:14px;height:14px;color:var(--cl-blue)}
        .cl-question-text{margin:11px 0 0;font-size:clamp(18px,2.2vw,23px);line-height:1.42;font-weight:620;letter-spacing:-.035em}
        .cl-disclosure{margin:14px 0 0;color:#60736d;font-size:11px;line-height:1.65;text-align:center}
        .cl-disclosure strong{color:#36555d}
        .cl-try-actions{display:flex;align-items:center;justify-content:center;gap:11px;margin-top:18px}
        .cl-try-actions .cl-button{min-height:47px}
        .cl-button-secondary{display:inline-flex;min-height:47px;align-items:center;justify-content:center;gap:8px;padding:0 17px;border:1px solid #c8d7d0;border-radius:999px;background:#f8faf5;color:#37565b;font-size:12px;font-weight:700}
        .cl-button-secondary:hover{background:#fff}.cl-button-secondary svg{width:15px;height:15px}
        .cl-interaction{margin:24px auto 0;border:1px solid #d7e2dc;border-radius:18px;background:#fffefa;box-shadow:0 17px 42px rgba(31,57,55,.08);overflow:hidden}
        .cl-interaction-head{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:15px 18px;border-bottom:1px solid #e8ede8;background:#fbfcf8}
        .cl-live-title{display:flex;align-items:center;gap:9px;font-size:12px;font-weight:750}
        .cl-live-dot{width:8px;height:8px;border-radius:50%;background:#9ca9a1}
        .cl-live-dot.on{background:#57a078;box-shadow:0 0 0 4px rgba(87,160,120,.12)}
        .cl-interaction-close{display:grid;place-items:center;width:36px;height:36px;border:1px solid transparent;border-radius:50%;background:transparent;color:#647873}
        .cl-interaction-close:hover{background:#eef3ed}.cl-interaction-close svg{width:17px;height:17px}
        .cl-session-meta{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:11px 18px;color:#708078;font-size:10px}
        .cl-session-status{display:flex;align-items:center;gap:7px}.cl-session-time{font-family:ui-monospace,monospace;font-variant-numeric:tabular-nums;color:#47636a}
        .cl-live-panel{padding:13px 18px 16px}
        .cl-audio-wave{height:54px;display:flex;align-items:center;justify-content:center;gap:3px;padding:0 3px;border-radius:11px;background:#f1f5ef}
        .cl-audio-wave i{width:4px;max-height:48px;min-height:3px;border-radius:4px;background:#9cb2a6;transition:height 65ms linear}
        .cl-audio-wave.has-audio i{background:#216e86}
        .cl-transcript{display:grid;gap:10px;max-height:202px;overflow:auto;padding:14px 2px 6px}
        .cl-message{max-width:88%;padding:10px 13px;border-radius:13px;font-size:12px;line-height:1.6;white-space:pre-wrap;overflow-wrap:anywhere}
        .cl-message.user{justify-self:end;border:1px solid #dbe5de;border-bottom-right-radius:4px;background:#f0f5ee;color:#36574d}
        .cl-message.assistant{justify-self:start;border:1px solid #e0e7ee;border-bottom-left-radius:4px;background:#f1f5fb;color:#2d4d61}
        .cl-empty-conversation{padding:8px 2px 5px;color:#829089;font-size:10px;line-height:1.55}
        .cl-error{margin:0 18px 13px;padding:12px 13px;border:1px solid #ebd3b9;border-radius:11px;background:#fff7ec;color:#72512d;font-size:11px;line-height:1.55}
        .cl-audio-permission{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 18px 13px;padding:12px;border:1px solid #d9e2eb;border-radius:12px;background:#f4f7fb;color:#526878;font-size:10px;line-height:1.5}
        .cl-audio-permission button{flex:none;min-height:38px;padding:0 12px;border:0;border-radius:999px;background:#315f7a;color:#fff;font-size:10px;font-weight:700}
        .cl-compose{display:flex;gap:8px;margin:0 18px 15px}
        .cl-compose input{flex:1;min-width:0;min-height:43px;padding:0 13px;border:1px solid #d9e3dd;border-radius:12px;background:#fffefa;color:var(--cl-ink);font-size:12px}
        .cl-compose input::placeholder{color:#92a099}
        .cl-send{display:grid;place-items:center;min-width:44px;min-height:43px;border:0;border-radius:12px;background:var(--cl-blue);color:white}
        .cl-send:disabled{cursor:not-allowed;background:#d2dcd7;color:#87958f}
        .cl-send svg{width:17px;height:17px}
        .cl-session-actions{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:0 18px 17px}
        .cl-mic-toggle,.cl-end-session{display:inline-flex;min-height:39px;align-items:center;justify-content:center;gap:7px;padding:0 12px;border:1px solid #d5dfd9;border-radius:999px;background:#fffefa;color:#566c67;font-size:10px;font-weight:700}
        .cl-mic-toggle svg,.cl-end-session svg{width:14px;height:14px}
        .cl-end-session{border-color:#e3d6d0;color:#845747;background:#fffaf7}
        .cl-mic-toggle:disabled{display:none}
        .cl-retry-path{display:flex;gap:9px;flex-wrap:wrap;margin:0 18px 16px}
        .cl-retry-path button{min-height:39px}
        .cl-process{padding:97px 0}
        .cl-process-heading{display:flex;justify-content:space-between;align-items:end;gap:30px;margin-bottom:36px}
        .cl-section-kicker{color:#426c78;font-size:10px;font-weight:850;letter-spacing:.15em;text-transform:uppercase}
        .cl-process-heading h2,.cl-control-layout h2,.cl-compat h2{margin:12px 0 0;font-size:clamp(38px,4.7vw,56px);line-height:1;letter-spacing:-.067em}
        .cl-process-heading p{max-width:350px;margin:0 0 4px;color:var(--cl-muted);font-size:13px;line-height:1.75}
        .cl-steps{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid #dce5de}
        .cl-step-card{padding:22px 18px 0 0}.cl-step-num{color:#61817b;font-family:ui-monospace,monospace;font-size:10px;font-weight:750}
        .cl-step-card h3{margin:24px 0 8px;font-size:15px;letter-spacing:-.03em}.cl-step-card p{max-width:230px;margin:0;color:#697a78;font-size:11px;line-height:1.7}
        .cl-control-section{position:relative;overflow:hidden;padding:78px 0;background:#1d3846;color:#f8f7ef}
        .cl-control-section:after{content:"";position:absolute;top:-290px;right:-150px;width:540px;height:540px;border:1px solid rgba(200,225,160,.18);border-radius:50%;box-shadow:0 0 0 50px rgba(200,225,160,.03),0 0 0 100px rgba(200,225,160,.025)}
        .cl-control-layout{position:relative;z-index:1;display:grid;grid-template-columns:1fr .9fr;align-items:center;gap:75px}
        .cl-control-layout .cl-section-kicker{color:#c7dc83}.cl-control-layout h2{max-width:520px;margin-top:14px}
        .cl-control-layout>div>p{max-width:460px;color:#bdcbc7;font-size:13px;line-height:1.75}
        .cl-control-list{display:grid;gap:0;margin:0;padding:0;border-top:1px solid rgba(255,255,255,.18)}
        .cl-control-list li{display:flex;align-items:center;gap:13px;padding:14px 0;border-bottom:1px solid rgba(255,255,255,.15);list-style:none;color:#edf1e9;font-size:12px}
        .cl-check{display:grid;place-items:center;width:25px;height:25px;border-radius:50%;background:rgba(197,220,131,.14);color:#d7e99d}.cl-check svg{width:13px;height:13px}
        .cl-compat{padding:84px 0}.cl-compat-layout{display:grid;grid-template-columns:1.1fr .8fr;align-items:center;gap:80px}
        .cl-compat-copy{max-width:510px;color:var(--cl-muted);font-size:13px;line-height:1.8}
        .cl-compat-note{padding:23px 24px;border-left:2px solid #9dbd79;background:#f0f3e8}
        .cl-compat-note strong{font-size:12px}.cl-compat-note p{margin:9px 0 0;color:#65746c;font-size:11px;line-height:1.7}
        .cl-cta{padding:0 0 78px}.cl-cta-panel{min-height:195px;display:flex;justify-content:space-between;align-items:center;gap:24px;padding:38px 45px;border-radius:22px;background:#e8f1eb}
        .cl-cta-panel h2{max-width:580px;margin:0;font-size:clamp(32px,4vw,46px);line-height:1.03;letter-spacing:-.06em}.cl-cta-panel p{margin:11px 0 0;color:#63776c;font-size:12px}
        .cl-footer{padding:22px 0 28px;border-top:1px solid #e1e8e2}.cl-footer-inner{display:flex;justify-content:space-between;align-items:center;gap:20px}
        .cl-footer small{color:#7b8983;font-size:10px}.cl-footer-links{display:flex;gap:20px;color:#687a74;font-size:10px}
        @media(max-width:1000px){
          .cl-hero{height:590px}.cl-orbit-symbol{min-width:39px;height:39px;padding:0 9px;font-size:18px}
          .symbol-1{left:4%}.symbol-5{right:4%}.symbol-6{right:1%}.symbol-12{left:1%}
          .symbol-13{left:7%}.symbol-14{right:7%}.symbol-15{left:1%;bottom:18%}.symbol-16{right:1%;bottom:18%}
          .cl-control-layout{gap:40px}.cl-compat-layout{gap:45px}
        }
        @media(max-width:700px){
          .cl-shell{width:calc(100% - 36px)}.cl-header{height:68px}.cl-nav{display:none}
          .cl-menu-toggle{display:inline-flex}
          .cl-menu-panel{position:absolute;top:61px;right:0;display:grid;width:min(290px,calc(100vw - 36px));gap:3px;padding:10px;border:1px solid var(--cl-line);border-radius:16px;background:#fffefa;box-shadow:0 16px 35px rgba(23,45,59,.12)}
          .cl-menu-panel a,.cl-menu-panel button{min-height:46px;padding:0 12px;border:0;border-radius:10px;background:transparent;color:var(--cl-ink);display:flex;align-items:center;justify-content:space-between;font-size:13px;font-weight:650}
          .cl-menu-panel a:hover{background:#f2f5ed}.cl-menu-panel .cl-button{justify-content:center;margin-top:3px;background:var(--cl-blue);color:white}
          .cl-hero{height:610px;display:block;padding-top:155px}.cl-hero-core{padding:0 8px;margin:0 auto}
          .cl-hero h1{font-size:clamp(46px,10.5vw,70px);margin-top:17px}.cl-hero-copy{max-width:450px;font-size:13px;line-height:1.68}
          .cl-hero:after{width:92vw;height:390px;top:48%}
          .cl-orbit-symbol{min-width:34px;height:34px;padding:0 7px;border-radius:11px;font-size:15px;box-shadow:0 6px 14px rgba(36,66,66,.065)}
          .cl-orbit-symbol.letters{font-size:13px}.cl-orbit-symbol.quote{font-size:13px}.cl-orbit-symbol.punct{font-size:18px}
          .symbol-1{left:6%;top:5%}.symbol-2{left:31%;top:2%}.symbol-3{left:58%;top:3%}.symbol-4{right:7%;top:7%}.symbol-5{right:1%;top:31%}
          .symbol-6{right:3%;top:auto;bottom:23%}.symbol-7{right:8%;bottom:12%}.symbol-8{right:30%;bottom:4%}.symbol-9{left:6%;bottom:7%}
          .symbol-10{left:29%;bottom:4%}.symbol-11{left:5%;bottom:23%}.symbol-12{left:0;top:35%}.symbol-13{left:1%;top:18%}
          .symbol-14{right:3%;top:20%}.symbol-15{left:24%;top:20%;bottom:auto}.symbol-16{right:24%;top:20%;bottom:auto}.symbol-17{left:17%;top:8%}.symbol-18{right:17%;top:8%}
          .cl-try{padding:47px 0 62px}.cl-try-inner{width:100%}.cl-question{padding:17px}.cl-question-text{font-size:18px}
          .cl-disclosure{text-align:left;font-size:10px}.cl-try-actions{align-items:stretch;flex-direction:column}.cl-try-actions .cl-button,.cl-try-actions .cl-button-secondary{width:100%}
          .cl-interaction-head{padding:12px 13px}.cl-session-meta{padding:10px 13px}.cl-live-panel{padding:11px 13px 13px}
          .cl-error,.cl-audio-permission{margin-left:13px;margin-right:13px}.cl-compose{margin-left:13px;margin-right:13px}.cl-session-actions{padding-left:13px;padding-right:13px}
          .cl-retry-path{margin-left:13px;margin-right:13px}.cl-audio-wave{gap:2px}.cl-audio-wave i{width:3px}
          .cl-process{padding:70px 0}.cl-process-heading{display:block;margin-bottom:28px}.cl-process-heading p{margin-top:15px}
          .cl-steps{grid-template-columns:1fr 1fr}.cl-step-card{min-height:150px;padding:17px 12px 17px 0;border-bottom:1px solid #dce5de}
          .cl-step-card:nth-child(odd){border-right:1px solid #dce5de}.cl-step-card:nth-child(even){padding-left:15px}
          .cl-step-card h3{margin-top:18px;font-size:13px}.cl-step-card p{font-size:10px}
          .cl-control-section{padding:65px 0}.cl-control-layout{grid-template-columns:1fr;gap:27px}.cl-control-layout>div>p{font-size:12px}
          .cl-compat{padding:65px 0}.cl-compat-layout{grid-template-columns:1fr;gap:24px}.cl-compat-copy{font-size:12px}
          .cl-cta{padding-bottom:56px}.cl-cta-panel{min-height:0;display:block;padding:26px 23px}.cl-cta-panel .cl-button{width:100%;margin-top:20px}
          .cl-footer-inner{align-items:flex-start;flex-direction:column}.cl-footer-links{gap:14px;flex-wrap:wrap}
        }
        @media(max-width:390px){
          .cl-shell{width:calc(100% - 28px)}.cl-hero{height:600px;padding-top:163px}
          .cl-hero h1{font-size:clamp(36px,11.2vw,54px)}.cl-hero-copy{font-size:12px}
          .cl-orbit-symbol{min-width:29px;height:29px;padding:0 6px;border-radius:9px;font-size:13px}
          .cl-orbit-symbol.letters{font-size:11px}.cl-orbit-symbol.quote{font-size:11px}.cl-orbit-symbol.punct{font-size:15px}
          .symbol-1{left:4%;top:6%}.symbol-2{left:29%;top:2%}.symbol-3{left:60%;top:3%}.symbol-4{right:4%;top:8%}
          .symbol-5{right:0;top:34%}.symbol-6{right:1%;top:auto;bottom:24%}.symbol-7{right:6%;bottom:10%}.symbol-8{right:26%;bottom:3%}
          .symbol-9{left:5%;bottom:7%}.symbol-10{left:29%;bottom:3%}.symbol-11{left:3%;bottom:24%}.symbol-12{display:none}
          .symbol-13{left:1%;top:21%}.symbol-14{right:2%;top:22%}.symbol-15{left:25%;top:18%;bottom:auto}.symbol-16{right:25%;top:18%;bottom:auto}
          .symbol-17{left:15%;top:10%}.symbol-18{right:15%;top:10%}
          .cl-message{max-width:96%}.cl-audio-wave{gap:1px}
        }
        @media(max-width:340px){.symbol-13,.symbol-14,.symbol-15,.symbol-16{display:none}}
        @media(prefers-reduced-motion:reduce){
          .claros-home *, .claros-home *:before, .claros-home *:after{animation-duration:.01ms!important;animation-iteration-count:1!important;scroll-behavior:auto!important;transition-duration:.01ms!important}
        }
      `}</style>

      <header className="cl-shell cl-header">
        <a href="#top" className="cl-brand" aria-label="Claros home" onClick={(event) => { event.preventDefault(); scrollTo("top"); }}>
          <BrandMark /> Claros
        </a>
        <nav className="cl-nav" aria-label="Main navigation">
          <a href="#how-it-works">How it works</a>
          <a href="#student-control">Student control</a>
          <a href="#accessibility">Worksheet fit</a>
          <button className="cl-button" onClick={() => scrollTo("try-it")}>Try it <ArrowRight /></button>
        </nav>
        <button className="cl-menu-toggle" aria-label={menuOpen ? "Close navigation" : "Open navigation"} aria-expanded={menuOpen} onClick={() => setMenuOpen((open) => !open)}>
          {menuOpen ? <X /> : <Menu />}
        </button>
        {menuOpen && (
          <nav className="cl-menu-panel" aria-label="Mobile navigation">
            <a href="#how-it-works" onClick={() => setMenuOpen(false)}>How it works <ChevronDown /></a>
            <a href="#student-control" onClick={() => setMenuOpen(false)}>Student control <ChevronDown /></a>
            <a href="#accessibility" onClick={() => setMenuOpen(false)}>Worksheet fit <ChevronDown /></a>
            <button className="cl-button" onClick={() => scrollTo("try-it")}>Try it <ArrowRight /></button>
          </nav>
        )}
      </header>

      <main id="top">
        <section className="cl-shell cl-hero" aria-labelledby="hero-title">
          {orbitSymbols.map((item) => (
            <span key={item.pos} className={`cl-orbit-symbol ${item.kind} ${item.pos}`} aria-hidden="true">{item.glyph}</span>
          ))}
          <div className="cl-hero-core">
            <div className="cl-eyebrow"><span className="cl-eyebrow-dot" /> A worksheet companion for your way of working</div>
            <h1 id="hero-title">Think it. Say it.<br /><span>Put it on the page.</span></h1>
            <p className="cl-hero-copy">Talk through a question or say the answer you know. Claros gives your thinking room—then lets you decide what belongs on the page.</p>
            <div className="cl-hero-actions"><button className="cl-button" onClick={() => scrollTo("try-it")}>Try a question <ArrowRight /></button></div>
            <p className="cl-hero-under">A short conversation. Your own words. Your call.</p>
          </div>
          <button className="cl-hero-down" aria-label="Scroll to Try it" onClick={() => scrollTo("try-it")}><ArrowDown /></button>
        </section>

        <section className="cl-try" id="try-it" aria-labelledby="try-heading">
          <div className="cl-shell cl-try-inner">
            <div className="cl-try-kicker">Try it</div>
            <h2 id="try-heading">Pick a question to think through.</h2>
            <div className="cl-topic-row" role="group" aria-label="Choose a sample question">
              <button type="button" className={`cl-topic ${selectedId === "math" ? "selected" : ""}`} disabled={lockedTopic} aria-pressed={selectedId === "math"} onClick={() => setSelectedId("math")}>Math</button>
              <button type="button" className={`cl-topic ${selectedId === "english" ? "selected" : ""}`} disabled={lockedTopic} aria-pressed={selectedId === "english"} onClick={() => setSelectedId("english")}>English</button>
            </div>
            <div className="cl-question">
              <div className="cl-question-subject"><FileText /> {selectedQuestion.subject} question</div>
              <p className="cl-question-text">{selectedQuestion.question}</p>
            </div>
            <p className="cl-disclosure">
              <strong>Before you start:</strong> This is a live AI conversation. In voice mode, microphone audio and conversation text are sent to OpenAI; in text mode, your messages are sent to OpenAI. Talk it through asks your browser for microphone permission after you click. Please don’t share personal information. The session lasts up to two minutes. No PDF is uploaded or changed.
            </p>
            <div className="cl-try-actions">
              <button className="cl-button" disabled={lockedTopic} onClick={openWithVoice}><Mic /> Talk it through <ArrowRight /></button>
              <button className="cl-button-secondary" disabled={lockedTopic} onClick={openWithText}>Type instead</button>
            </div>

            {panelOpen && (
              <section ref={panelRef} tabIndex={-1} className="cl-interaction" aria-label="Live question conversation">
                <div className="cl-interaction-head">
                  <div className="cl-live-title"><span className={`cl-live-dot ${demo.active ? "on" : ""}`} /> Question conversation <span className="cl-sr-only" aria-live="polite">{currentStatus}</span></div>
                  <button className="cl-interaction-close" aria-label="Close conversation" onClick={closeInteraction}><X /></button>
                </div>
                <div className="cl-session-meta">
                  <span className="cl-session-status" role="status" aria-live="polite">{currentStatus}</span>
                  <span className="cl-session-time">{elapsedLabel} <span aria-hidden="true">/</span> 2:00</span>
                </div>
                <div className="cl-live-panel">
                  <AudioWave level={demo.audioLevel} active={demo.status === "speaking"} />
                  <div className="cl-transcript" aria-label="Conversation">
                    {demo.messages.length ? demo.messages.map((message) => (
                      <div key={message.id} className={`cl-message ${message.role}`}>{message.text}</div>
                    )) : (
                      <p className="cl-empty-conversation">{demo.status === "connecting" ? "Getting the conversation ready…" : demo.status === "error" ? "No conversation started. You can try again or type instead." : "When your conversation begins, your words and Claros’s replies will appear here."}</p>
                    )}
                  </div>
                </div>
                {demo.needsAudioPermission && (
                  <div className="cl-audio-permission">
                    <span>Your browser is blocking reply audio. Allow sound to hear Claros.</span>
                    <button onClick={() => void demo.resumeAudio()}>Enable sound</button>
                  </div>
                )}
                {demo.error && <p className="cl-error" role="alert">{demo.error}</p>}
                {["ready", "listening", "thinking", "speaking"].includes(demo.status) && (
                  <form className="cl-compose" onSubmit={submitText}>
                    <input
                      value={typedMessage}
                      onChange={(event) => setTypedMessage(event.target.value.slice(0, 1000))}
                      maxLength={1000}
                      aria-label="Type a thought or question"
                      placeholder="Type a thought or question…"
                      disabled={!["ready", "listening"].includes(demo.status)}
                    />
                    <button className="cl-send" type="submit" aria-label="Send message" disabled={!canSend}><Send /></button>
                  </form>
                )}
                {demo.status === "connecting" && (
                  <p className="cl-empty-conversation" style={{ padding: "0 18px 16px" }}>Connecting only after your request. You can close this panel at any time.</p>
                )}
                {(demo.status === "error" || demo.status === "ended" || demo.status === "idle") && (
                  <div className="cl-retry-path">
                    <button className="cl-button" onClick={() => startAgain("voice")}><Mic /> Try voice again</button>
                    <button className="cl-button-secondary" onClick={() => startAgain("text")}>Continue by typing</button>
                  </div>
                )}
                {(demo.active || demo.status === "connecting") && (
                  <div className="cl-session-actions">
                    {demo.hasMicrophone && (
                      <button className="cl-mic-toggle" onClick={demo.toggleMicrophone}>
                        {demo.micEnabled ? <><Mic /> Mute microphone</> : <><MicOff /> Unmute microphone</>}
                      </button>
                    )}
                    <button className="cl-end-session" onClick={closeInteraction}><X /> End conversation</button>
                  </div>
                )}
              </section>
            )}
          </div>
        </section>

        <section className="cl-shell cl-process" id="how-it-works">
          <div className="cl-process-heading">
            <div><div className="cl-section-kicker">From a thought to a worksheet</div><h2>One question at a time.<br />Always yours.</h2></div>
            <p>Claros makes room for how you think without taking over your answer. The conversation can help you work something out; your final words stay yours.</p>
          </div>
          <ol className="cl-steps">
            <li className="cl-step-card"><span className="cl-step-num">01 / SAY</span><h3>Start with your thought</h3><p>Speak an answer you know or talk through the part that feels tricky.</p></li>
            <li className="cl-step-card"><span className="cl-step-num">02 / WORK</span><h3>Keep working it out</h3><p>Explore the question and follow the idea that helps you think.</p></li>
            <li className="cl-step-card"><span className="cl-step-num">03 / REVIEW</span><h3>Edit a separate draft</h3><p>Make the wording sound like you before anything gets added.</p></li>
            <li className="cl-step-card"><span className="cl-step-num">04 / APPROVE</span><h3>Choose what goes in</h3><p>Only an answer you explicitly approve can enter a new completed PDF.</p></li>
          </ol>
        </section>

        <section className="cl-control-section" id="student-control">
          <div className="cl-shell cl-control-layout">
            <div><div className="cl-section-kicker">Student control</div><h2>Your answer stays yours.</h2><p>Talking can help you get your thoughts out. It does not decide what counts as your answer. That choice stays with you.</p></div>
            <ul className="cl-control-list">
              <li><span className="cl-check"><Check /></span> Your words stay in an editable draft</li>
              <li><span className="cl-check"><Check /></span> Exact wording is shown before approval</li>
              <li><span className="cl-check"><Check /></span> Nothing is placed without your say-so</li>
              <li><span className="cl-check"><Check /></span> Your original PDF remains unchanged</li>
            </ul>
          </div>
        </section>

        <section className="cl-shell cl-compat" id="accessibility">
          <div className="cl-compat-layout">
            <div><div className="cl-section-kicker">Voice-first, never voice-only</div><h2>Use the way that works for you.</h2><p className="cl-compat-copy">Speak when typing is difficult. Type when that feels easier. Switch between them while keeping your place, your thinking, and the final decision in your hands.</p></div>
            <aside className="cl-compat-note"><strong>Works with text-based short-answer PDFs</strong><p>Claros supports worksheets up to 8 pages and 40 questions. Scanned PDFs aren’t supported. If an approved answer won’t fit safely beside its question, it goes on an attached answer page.</p></aside>
          </div>
        </section>

        <section className="cl-shell cl-cta">
          <div className="cl-cta-panel"><div><h2>Ready to think out loud?</h2><p>Pick a question and start a short conversation when you’re ready.</p></div><button className="cl-button" onClick={() => scrollTo("try-it")}>Try it <ArrowRight /></button></div>
        </section>
      </main>
      <footer className="cl-footer">
        <div className="cl-shell cl-footer-inner">
          <a href="#top" className="cl-brand" aria-label="Claros home" onClick={(event) => { event.preventDefault(); scrollTo("top"); }}><BrandMark /> Claros</a>
          <small>Speak, think, decide.</small>
          <div className="cl-footer-links"><a href="#how-it-works">How it works</a><a href="#accessibility">Worksheet fit</a><a href="#try-it">Try it</a></div>
        </div>
      </footer>
    </div>
  );
}