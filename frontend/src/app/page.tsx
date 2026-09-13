import { HealthStatus } from "@/components/health-status";

const foundationItems = [
  {
    number: "01",
    title: "Local web foundation",
    detail:
      "A focused Next.js shell built for a Windows-first development workflow.",
  },
  {
    number: "02",
    title: "Observable API boundary",
    detail:
      "A FastAPI health contract proves that the browser and local backend can communicate.",
  },
  {
    number: "03",
    title: "Safe by default",
    detail:
      "Environment-based configuration keeps local settings and future credentials separated.",
  },
];

export default function Home() {
  return (
    <main>
      <header className="site-header">
        <a
          className="brand"
          href="#main-content"
          aria-label="Subtitle Forge home"
        >
          <svg
            className="brand__mark"
            viewBox="0 0 40 40"
            role="img"
            aria-label="Subtitle Forge mark"
          >
            <path d="M8 10h18a6 6 0 0 1 6 6v2H14a6 6 0 0 1-6-6v-2Z" />
            <path d="M32 30H14a6 6 0 0 1-6-6v-2h18a6 6 0 0 1 6 6v2Z" />
          </svg>
          <span>Subtitle Forge</span>
        </a>
        <span className="phase-chip">Phase 0 · Foundation</span>
      </header>

      <section className="hero" id="main-content">
        <div className="hero__copy">
          <p className="eyebrow">Media → subtitles → knowledge</p>
          <h1>Subtitle Forge</h1>
          <p className="hero__label">AI bilingual media knowledge tool</p>
          <p className="hero__summary">
            A local-first foundation for turning video and audio into bilingual,
            timestamp-aware knowledge—without making a paid AI service
            mandatory.
          </p>
          <p className="phase-note">
            <span className="phase-note__line" aria-hidden="true" />
            Media processing arrives in Phase 1. This Phase 0 foundation
            verifies the web and API connection first.
          </p>
        </div>

        <aside className="system-card" aria-labelledby="system-heading">
          <div className="system-card__topline">
            <p id="system-heading">Local system status</p>
            <span aria-hidden="true">SF—00</span>
          </div>
          <HealthStatus />
          <div
            className="system-map"
            aria-label="Phase 0 application connection"
          >
            <div>
              <span className="system-map__label">Browser</span>
              <strong>Next.js UI</strong>
            </div>
            <span className="system-map__connector" aria-hidden="true">
              <i />
            </span>
            <div>
              <span className="system-map__label">Local API</span>
              <strong>FastAPI</strong>
            </div>
          </div>
          <p className="system-card__caption">
            No media is uploaded or processed in this foundation phase.
          </p>
        </aside>
      </section>

      <section className="foundation" aria-labelledby="foundation-heading">
        <div className="section-heading">
          <p className="eyebrow">Built before the workflow</p>
          <h2 id="foundation-heading">
            A dependable base, deliberately small.
          </h2>
        </div>
        <div className="foundation__grid">
          {foundationItems.map((item) => (
            <article className="foundation-card" key={item.number}>
              <span className="foundation-card__number">{item.number}</span>
              <h3>{item.title}</h3>
              <p>{item.detail}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="roadmap" aria-labelledby="roadmap-heading">
        <div>
          <p className="eyebrow">Product direction</p>
          <h2 id="roadmap-heading">Local first. SaaS later.</h2>
        </div>
        <ol className="roadmap__steps">
          <li className="roadmap__step roadmap__step--active">
            <span>Now</span>
            <strong>Foundation</strong>
          </li>
          <li className="roadmap__step">
            <span>Next</span>
            <strong>Bilingual media workflow</strong>
          </li>
          <li className="roadmap__step">
            <span>Later</span>
            <strong>Timestamp-cited knowledge</strong>
          </li>
        </ol>
      </section>

      <footer>
        <span>Subtitle Forge</span>
        <span>Open source · Local first · Timestamp aware</span>
      </footer>
    </main>
  );
}
