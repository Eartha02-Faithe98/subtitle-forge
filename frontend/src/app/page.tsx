import { Phase1Workflow } from "@/components/phase1-workflow";

export default function Home() {
  return (
    <main>
      <header className="site-header">
        <a className="brand" href="#workflow" aria-label="Subtitle Forge 首頁">
          <svg
            className="brand__mark"
            viewBox="0 0 40 40"
            role="img"
            aria-label="Subtitle Forge 標誌"
          >
            <path d="M8 10h18a6 6 0 0 1 6 6v2H14a6 6 0 0 1-6-6v-2Z" />
            <path d="M32 30H14a6 6 0 0 1-6-6v-2h18a6 6 0 0 1 6 6v2Z" />
          </svg>
          <span>Subtitle Forge</span>
        </a>
        <span className="phase-chip">Phase 1 · Local MVP</span>
      </header>

      <section className="hero" aria-labelledby="hero-heading">
        <div>
          <p className="eyebrow">Local media intelligence</p>
          <h1 id="hero-heading">把媒體鍛造成雙語字幕。</h1>
          <p className="hero__summary">
            輸入 YouTube、MP3 或 MP4，以 Local Whisper 轉錄英文，透過本機 Ollama
            相容模型產生繁體中文翻譯與雙語摘要。
          </p>
        </div>
        <dl className="capability-list" aria-label="Phase 1 能力">
          <div>
            <dt>輸入</dt>
            <dd>YouTube · MP3 · MP4</dd>
          </div>
          <div>
            <dt>處理</dt>
            <dd>Local Whisper · 繁中翻譯</dd>
          </div>
          <div>
            <dt>輸出</dt>
            <dd>逐字稿 · SRT · 摘要</dd>
          </div>
          <div>
            <dt>資料</dt>
            <dd>儲存於本機工作目錄</dd>
          </div>
        </dl>
      </section>

      <div id="workflow">
        <Phase1Workflow />
      </div>

      <footer>
        <span>Subtitle Forge</span>
        <span>Open source · Local first · Timestamp aware</span>
      </footer>
    </main>
  );
}
