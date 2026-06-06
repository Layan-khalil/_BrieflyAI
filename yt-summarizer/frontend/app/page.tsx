'use client';

import { useState, useEffect, useRef, useCallback } from 'react';

interface SummaryData {
  summary: string;
  key_insights: string[];
  bullet_notes: string[];
  timestamps: Array<{ time: string; topic: string }>;
}

interface Metadata {
  title: string;
  channel: string;
  duration: number;
  thumbnail: string;
}

function extractVideoId(url: string): string | null {
  const match = url.match(/(?:v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
  return match?.[1] ?? null;
}

function isValidYoutubeUrl(url: string): boolean {
  return /(?:youtube\.com|youtu\.be)/.test(url);
}

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

export default function Home() {
  const [url, setUrl] = useState('');
  const [language, setLanguage] = useState<'en' | 'ar'>('en');
  const [loading, setLoading] = useState(false);
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [data, setData] = useState<SummaryData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [urlError, setUrlError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [loadStep, setLoadStep] = useState(0);
  const resultsRef = useRef<HTMLDivElement>(null);
  const t = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dir = language === 'ar' ? 'rtl' : 'ltr';
  }, [language]);
  useEffect(() => {
    fetch('https://brieflyai.up.railway.app/health');
  }, []);
  const showToast = useCallback((msg: string) => {
    setToast(msg);
    if (t.current) clearTimeout(t.current);
    t.current = setTimeout(() => setToast(null), 2500);
  }, []);

  const handleUrlChange = (value: string) => {
    setUrl(value);
    if (urlError) setUrlError(null);
    if (error) setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setData(null);
    setMetadata(null);
    setError(null);
    setUrlError(null);

    const trimmed = url.trim();
    if (!trimmed) {
      setUrlError(T('Please enter a YouTube link.', 'يرجى إدخال رابط يوتيوب.'));
      return;
    }
    if (!isValidYoutubeUrl(trimmed)) {
      setUrlError(T('Please enter a valid YouTube link.', 'يرجى إدخال رابط يوتيوب صحيح.'));
      return;
    }
    if (!extractVideoId(trimmed)) {
      setUrlError(T('Could not extract video ID from this link.', 'تعذر استخراج معرف الفيديو من هذا الرابط.'));
      return;
    }

    setLoading(true);
    setLoadStep(0);
    const si = setInterval(() => setLoadStep(prev => Math.min(prev + 1, 3)), 1000);
    try {
      setLoadStep(1);
      const backendUrl = typeof window !== 'undefined' && window.location.hostname === 'localhost'
        ? 'http://localhost:8002'
        : 'https://brieflyai.up.railway.app';
      const res = await fetch(`${backendUrl}/api/summarize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: trimmed, language }),
      });
      setLoadStep(2);
      if (!res.ok) {
        const ed = await res.json();
        throw new Error(ed.detail || 'Request failed');
      }
      setLoadStep(3);
      const result = await res.json();
      setMetadata(result.metadata);
      setData(result.analysis);
      clearInterval(si);
      setTimeout(() => resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 150);
    } catch (err) {
      clearInterval(si);
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
      setLoadStep(0);
    }
  };

  const formatAllSections = () => {
    if (!data) return '';
    const ar = language === 'ar';
    let text = `${ar ? 'الملخص' : 'Summary'}:\n${data.summary}\n\n`;
    text += `${ar ? 'أهم الرؤى' : 'Key Insights'}:\n${data.key_insights.map((x, i) => `${i + 1}. ${x}`).join('\n')}\n\n`;
    if (data.bullet_notes?.length) {
      text += `${ar ? 'ملاحظات مفصلة' : 'Detailed Notes'}:\n${data.bullet_notes.map((x, i) => `${i + 1}. ${x}`).join('\n')}\n\n`;
    }
    if (data.timestamps?.length) {
      text += `${ar ? 'الطوابع الزمنية' : 'Timestamps'}:\n${data.timestamps.map(t => `[${t.time}] ${t.topic}`).join('\n')}\n`;
    }
    return text;
  };

  const copyText = () => {
    if (!data) return;
    navigator.clipboard.writeText(formatAllSections());
    showToast(language === 'ar' ? 'تم النسخ!' : 'Copied!');
  };

  const exportTxt = () => {
    if (!data) return;
    const blob = new Blob([formatAllSections()], { type: 'text/plain;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `brieflyai_summary_${language}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
  };

  const switchLanguage = (lang: 'en' | 'ar') => {
    setLanguage(lang);
    setData(null);
    setMetadata(null);
    setError(null);
  };

  const T = (en: string, ar: string) => language === 'ar' ? ar : en;

  const vid = extractVideoId(url);
  const hasResults = data && metadata;

  return (
    <div className="min-h-screen relative overflow-x-hidden" style={{ background: '#0a0912' }}>
      {/* Gradient bg */}
      <div className="fixed inset-0 pointer-events-none z-0"
        style={{
          background: `
            radial-gradient(70% 55% at 50% -8%, rgba(124,58,237,0.14), transparent 60%),
            radial-gradient(50% 45% at 90% 110%, rgba(99,102,241,0.08), transparent 60%)
          `
        }}
      />

      {/* ─── TOP BAR ─── */}
      <header className="relative z-10 flex items-center justify-between px-6 sm:px-8 py-4 border-b" style={{ borderColor: '#262333' }}>
        <div className="flex items-center gap-3">
          <span className="text-xl font-extrabold tracking-tight">
            <span style={{ color: '#ededf2' }}>Briefly</span><span style={{ color: '#a78bfa' }}>AI</span>
          </span>
        </div>
        <div className="flex items-center gap-0.5 p-0.5 rounded-[10px] border" style={{ background: '#15131f', borderColor: '#262333' }}>
          <button
            onClick={() => switchLanguage('en')}
            className="text-xs font-semibold px-3 py-1.5 rounded-[7px] transition"
            style={language === 'en' ? { background: 'rgba(139,92,246,0.12)', color: '#a78bfa', boxShadow: 'inset 0 0 0 1px rgba(139,92,246,0.35)' } : { color: '#6a6878' }}
          >EN</button>
          <button
            onClick={() => switchLanguage('ar')}
            className="text-xs font-semibold px-3 py-1.5 rounded-[7px] transition"
            style={language === 'ar' ? { background: 'rgba(139,92,246,0.12)', color: '#a78bfa', boxShadow: 'inset 0 0 0 1px rgba(139,92,246,0.35)' } : { color: '#6a6878' }}
          >AR</button>
        </div>
      </header>

      {/* ─── LANDING ─── */}
      {!loading && !hasResults && (
        <section className="relative z-10 min-h-[calc(100vh-70px)] flex flex-col">
          <div className="flex-1 flex flex-col items-center justify-center text-center px-6 py-16 w-full max-w-[680px] mx-auto">
            <h1 className="text-[clamp(30px,4.4vw,46px)] font-extrabold leading-[1.12] tracking-tight mb-[18px] balance">
              {language === 'ar' ? (
                <>لخّص أي فيديو <span style={{ color: '#a78bfa' }}>بثوانٍ</span></>
              ) : (
                <>Summarize any <span style={{ color: '#a78bfa' }}>YouTube</span> video in seconds</>
              )}
            </h1>
            <p className="text-base mb-[34px] leading-relaxed" style={{ color: '#9b99ab' }}>
              {T(
                'Paste a link and get structured insights — summary, key points, and timestamps.',
                'الصق الرابط واحصل على ملخص منظم — خلاصة، نقاط رئيسية، وطوابع زمنية.'
              )}
            </p>

            <form onSubmit={handleSubmit} className="flex items-stretch gap-3 w-full max-w-[600px]">
              <div className="flex-1 flex items-center gap-3 px-4 rounded-[13px] border transition-all"
                style={{
                  background: '#15131f',
                  borderColor: urlError ? '#ef4444' : '#262333',
                  boxShadow: urlError ? '0 0 0 4px rgba(239,68,68,0.12)' : 'none',
                }}
                onFocus={(e) => {
                  if (!urlError) {
                    (e.currentTarget as HTMLElement).style.borderColor = '#8b5cf6';
                    (e.currentTarget as HTMLElement).style.boxShadow = '0 0 0 4px rgba(139,92,246,0.12)';
                  }
                }}
                onBlur={(e) => {
                  if (!urlError) {
                    (e.currentTarget as HTMLElement).style.borderColor = '#262333';
                    (e.currentTarget as HTMLElement).style.boxShadow = 'none';
                  }
                }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ color: '#6a6878', flexShrink: 0 }}>
                  <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
                  <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
                </svg>
                <input
                  type="text"
                  value={url}
                  onChange={(e) => handleUrlChange(e.target.value)}
                  placeholder={T('Paste YouTube link here...', 'الصق رابط يوتيوب هنا...')}
                  className="flex-1 bg-transparent border-0 outline-none text-[15px] py-[15px] min-w-0"
                  style={{ color: '#ededf2' }}
                  required
                />
              </div>
              <button type="submit" disabled={loading}
                className="inline-flex items-center justify-center gap-2 px-6 font-bold text-[15px] rounded-[13px] border-0 whitespace-nowrap transition-all"
                style={{
                  background: 'linear-gradient(135deg,#8b5cf6,#7c3aed)',
                  color: '#fff',
                  boxShadow: '0 6px 22px rgba(124,58,237,0.45)',
                }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.filter = 'brightness(1.07)'; (e.currentTarget as HTMLElement).style.transform = 'translateY(-1px)'; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.filter = 'none'; (e.currentTarget as HTMLElement).style.transform = 'none'; }}
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    {T('Summarizing...', 'يُلخّص...')}
                  </span>
                ) : T('Summarize', 'لخّص')}
              </button>
            </form>

            {urlError && (
              <div className="flex items-center gap-2 mt-3 text-xs animate-fade-in" style={{ color: '#ef4444', animation: 'fade-up .25s ease-out' }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                <span>{urlError}</span>
              </div>
            )}

            <div className="inline-flex items-center gap-2 mt-[22px] text-xs" style={{ color: '#6a6878' }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              <span>{T("Your privacy is protected — we don't store video data", 'خصوصيتك محمية — لا نخزّن بيانات الفيديو')}</span>
            </div>
          </div>
        </section>
      )}

      {/* ─── LOADING ─── */}
      {loading && (
        <section className="relative z-10 min-h-[calc(100vh-70px)] flex flex-col">
          <div className="flex-1 flex flex-col items-center justify-center gap-8 px-6 py-12">
            {/* Orb */}
            <div className="relative w-[120px] h-[120px] grid place-items-center">
              <div className="w-5 h-5 rounded-full" style={{ background: '#8b5cf6', boxShadow: '0 0 36px 6px rgba(124,58,237,0.45)', animation: 'pulse-glow 1.6s ease-in-out infinite' }} />
              {[54, 84, 114].map((s, i) => (
                <div key={i} className="absolute rounded-full border" style={{
                  width: s, height: s, borderColor: '#8b5cf6', opacity: 0.4,
                  animation: `ring-expand 2s ease-out infinite ${i * 0.35}s`
                }} />
              ))}
            </div>

            {/* Steps */}
            <ul className="flex flex-col gap-3 min-w-[260px] list-none p-0 m-0">
              {[
                T('Fetching video transcript...', 'جلب نص الفيديو...'),
                T('Analyzing content with AI...', 'تحليل المحتوى بالذكاء الاصطناعي...'),
                T('Structuring insights...', 'تنظيم الرؤى...'),
              ].map((label, i) => {
                const idx = i + 1;
                const done = loadStep > idx;
                const active = loadStep === idx;
                return (
                  <li key={i} className="flex items-center gap-3 text-sm" style={{
                    color: active ? '#ededf2' : done ? '#9b99ab' : '#6a6878',
                    transition: 'color .3s'
                  }}>
                    <span className="w-2 h-2 rounded-full shrink-0" style={{
                      background: active ? '#8b5cf6' : done ? '#8b5cf6' : '#322e44',
                      opacity: done ? 0.55 : 1,
                      boxShadow: active ? '0 0 12px rgba(124,58,237,0.45)' : 'none',
                      transition: 'all .3s'
                    }} />
                    {label}
                  </li>
                );
              })}
            </ul>

            <div className="text-xs px-3.5 py-1.5 rounded-[8px] max-w-[90vw] truncate"
              style={{ color: '#6a6878', background: '#15131f', borderColor: '#262333' }}
            >{url}</div>
          </div>
        </section>
      )}

      {/* ─── ERROR ─── */}
      {error && (
        <div className="relative z-10 max-w-[600px] mx-auto mt-6 px-6">
          <div className="flex items-center gap-3 px-4 py-3 rounded-[13px] text-sm" style={{
            background: 'rgba(239,68,68,0.12)',
            border: '1px solid rgba(239,68,68,0.35)',
            color: '#ededf2',
            animation: 'toast-in .3s ease-out'
          }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
            {error}
          </div>
        </div>
      )}

      {/* ─── RESULTS ─── */}
      {hasResults && (
        <section className="relative z-10" ref={resultsRef} style={{ animation: 'fade-up .5s ease-out' }}>
          <div className="max-w-[1240px] mx-auto px-4 sm:px-8 py-6 pb-16">
            <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.12fr] gap-5 items-start">

              {/* ─── LEFT COL: Cards ─── */}
              <div className="flex flex-col gap-3.5 min-w-0">

                {/* Video title */}
                <div className="flex items-start gap-3 p-4 rounded-[16px] border" style={{ background: '#15131f', borderColor: '#262333' }}>
                  <div className="w-[38px] h-[38px] shrink-0 rounded-[11px] grid place-items-center" style={{ background: 'rgba(245,158,11,0.14)', color: '#fbbf24' }}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>
                  </div>
                  <div className="min-w-0 flex-1">
                    <h2 className="text-[15px] font-bold mb-1">{metadata.title}</h2>
                    <p className="text-[13.5px] leading-relaxed" style={{ color: '#9b99ab' }}>
                      {metadata.channel}
                      {metadata.duration > 0 && <> &middot; {formatDuration(metadata.duration)}</>}
                    </p>
                  </div>
                </div>

                {/* Summary */}
                <div className="flex items-start gap-3 p-4 rounded-[16px] border" style={{ background: '#15131f', borderColor: '#262333' }}>
                  <div className="w-[38px] h-[38px] shrink-0 rounded-[11px] grid place-items-center" style={{ background: 'rgba(139,92,246,0.12)', color: '#a78bfa' }}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className="text-[15px] font-bold mb-1.5">{T('Summary', 'الملخص')}</h3>
                    <p className="text-[13.5px] leading-relaxed" style={{ color: '#9b99ab' }} dir={language === 'ar' ? 'rtl' : undefined}>{data.summary}</p>
                  </div>
                </div>

                {/* Key Insights */}
                {data.key_insights?.length > 0 && (
                  <div className="flex items-start gap-3 p-4 rounded-[16px] border" style={{ background: '#15131f', borderColor: '#262333' }}>
                    <div className="w-[38px] h-[38px] shrink-0 rounded-[11px] grid place-items-center" style={{ background: 'rgba(59,130,246,0.14)', color: '#60a5fa' }}>
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
                    </div>
                    <div className="min-w-0 flex-1">
                      <h3 className="text-[15px] font-bold mb-1.5">{T('Key Insights', 'أهم الرؤى')}</h3>
                      <ul className="flex flex-col gap-1.5 list-none p-0 m-0">
                        {data.key_insights.map((insight, i) => (
                          <li key={i} className={`relative text-[13.5px] leading-relaxed ${language === 'ar' ? 'pr-4' : 'pl-4'}`} style={{ color: '#9b99ab' }}>
                            <span className={`absolute top-2 w-[5px] h-[5px] rounded-full ${language === 'ar' ? 'right-0.5' : 'left-0.5'}`} style={{ background: '#6a6878' }} />
                            {insight}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}

                {/* Notes */}
                {data.bullet_notes?.length > 0 && (
                  <div className="flex items-start gap-3 p-4 rounded-[16px] border" style={{ background: '#15131f', borderColor: '#262333' }}>
                    <div className="w-[38px] h-[38px] shrink-0 rounded-[11px] grid place-items-center" style={{ background: 'rgba(34,197,94,0.13)', color: '#4ade80' }}>
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 20V10"/><path d="M18 20V4"/><path d="M6 20v-4"/></svg>
                    </div>
                    <div className="min-w-0 flex-1">
                      <h3 className="text-[15px] font-bold mb-1.5">{T('Detailed Notes', 'ملاحظات مفصلة')}</h3>
                      <ul className="flex flex-col gap-1.5 list-none p-0 m-0">
                        {data.bullet_notes.map((note, i) => (
                          <li key={i} className={`relative text-[13.5px] leading-relaxed ${language === 'ar' ? 'pr-4' : 'pl-4'}`} style={{ color: '#9b99ab' }}>
                            <span className={`absolute top-2 w-[5px] h-[5px] rounded-full ${language === 'ar' ? 'right-0.5' : 'left-0.5'}`} style={{ background: '#6a6878' }} />
                            {note}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}

                {/* Timestamps */}
                {data.timestamps?.length > 0 && (
                  <div className="flex items-start gap-3 p-4 rounded-[16px] border" style={{ background: '#15131f', borderColor: '#262333' }}>
                    <div className="w-[38px] h-[38px] shrink-0 rounded-[11px] grid place-items-center" style={{ background: 'rgba(245,158,11,0.14)', color: '#fbbf24' }}>
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                    </div>
                    <div className="min-w-0 flex-1">
                      <h3 className="text-[15px] font-bold mb-1.5">{T('Timestamps', 'الطوابع الزمنية')}</h3>
                      <ul className="flex flex-col gap-2 list-none p-0 m-0">
                        {data.timestamps.map((ts, i) => (
                          <li key={i} className="flex items-baseline gap-3 text-[13.5px]">
                            <span className="shrink-0 font-semibold min-w-[46px]" style={{ color: '#a78bfa' }}>{ts.time}</span>
                            <span style={{ color: '#9b99ab' }}>{ts.topic}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}

                {/* Action buttons */}
                <div className="grid grid-cols-2 gap-3 mt-1">
                  <button onClick={copyText}
                    className="flex items-center justify-center gap-3 px-3.5 py-2.5 rounded-[13px] text-sm cursor-pointer font-inherit transition-all"
                    style={{ background: '#15131f', border: '1px solid #322e44', color: '#ededf2' }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = '#8b5cf6'; (e.currentTarget as HTMLElement).style.background = '#1a1826'; }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = '#322e44'; (e.currentTarget as HTMLElement).style.background = '#15131f'; }}
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                    <span>{T('Copy text', 'نسخ النص')}</span>
                  </button>
                  <button onClick={exportTxt}
                    className="flex items-center justify-center gap-3 px-3.5 py-2.5 rounded-[13px] text-sm cursor-pointer font-inherit transition-all"
                    style={{ background: '#15131f', border: '1px solid #322e44', color: '#ededf2' }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.borderColor = '#8b5cf6'; (e.currentTarget as HTMLElement).style.background = '#1a1826'; }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.borderColor = '#322e44'; (e.currentTarget as HTMLElement).style.background = '#15131f'; }}
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#a78bfa" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                    <span>{T('Export text', 'تصدير النص')}</span>
                  </button>
                </div>

                {/* Toast */}
                {toast && (
                  <div className="flex items-center gap-3 px-4 py-2.5 rounded-[13px] text-sm mt-1" style={{
                    background: 'rgba(34,197,94,0.13)',
                    border: '1px solid rgba(34,197,94,0.35)',
                    color: '#ededf2',
                    animation: 'toast-in .3s ease-out'
                  }}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4ade80" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>
                    {toast}
                  </div>
                )}
              </div>

              {/* ─── RIGHT COL: Video ─── */}
              <div className="min-w-0">
                <div className="lg:sticky lg:top-6">
                  {vid ? (
                    <div className="rounded-[16px] overflow-hidden" style={{ background: '#000', border: '1px solid #262333' }}>
                      <iframe
                        src={`https://www.youtube.com/embed/${vid}`}
                        title={metadata.title}
                        className="w-full aspect-video block"
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                        allowFullScreen
                      />
                    </div>
                  ) : (
                    <div className="rounded-[16px] overflow-hidden" style={{ border: '1px solid #262333' }}>
                      <img src={metadata.thumbnail} alt={metadata.title} className="w-full block" />
                    </div>
                  )}
                </div>
              </div>

            </div>
          </div>
        </section>
      )}
    </div>
  );
}
