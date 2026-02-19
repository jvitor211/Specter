"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";

function useCursorCustom() {
  const cursorRef = useRef<HTMLDivElement>(null);
  const ringRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let mx = 0, my = 0, rx = 0, ry = 0;
    const cursor = cursorRef.current;
    const ring = ringRef.current;
    if (!cursor || !ring) return;

    const onMove = (e: MouseEvent) => {
      mx = e.clientX; my = e.clientY;
      cursor.style.left = `${mx}px`;
      cursor.style.top = `${my}px`;
    };

    let raf: number;
    const animRing = () => {
      rx += (mx - rx) * 0.12;
      ry += (my - ry) * 0.12;
      ring.style.left = `${rx}px`;
      ring.style.top = `${ry}px`;
      raf = requestAnimationFrame(animRing);
    };

    document.addEventListener("mousemove", onMove);
    raf = requestAnimationFrame(animRing);

    return () => {
      document.removeEventListener("mousemove", onMove);
      cancelAnimationFrame(raf);
    };
  }, []);

  return { cursorRef, ringRef };
}

function useRevealOnScroll() {
  useEffect(() => {
    const reveals = document.querySelectorAll(".reveal");
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) e.target.classList.add("visible");
        });
      },
      { threshold: 0.1 }
    );
    reveals.forEach((r) => io.observe(r));
    return () => io.disconnect();
  }, []);
}

function useCounterAnimation() {
  useEffect(() => {
    function animCount(el: HTMLElement, target: number) {
      let start: number | null = null;
      const step = (ts: number) => {
        if (!start) start = ts;
        const prog = Math.min((ts - start) / 1800, 1);
        const ease = 1 - Math.pow(1 - prog, 3);
        const val = Math.floor(ease * target);
        el.textContent =
          val >= 1000
            ? val.toLocaleString()
            : target === 20
              ? `${val}%`
              : String(val);
        if (prog < 1) requestAnimationFrame(step);
        else
          el.textContent =
            target >= 1000
              ? target.toLocaleString()
              : target === 20
                ? `${target}%`
                : String(target);
      };
      requestAnimationFrame(step);
    }

    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            const el = e.target as HTMLElement;
            const t = parseInt(el.dataset.target || "0");
            if (t) animCount(el, t);
            io.unobserve(el);
          }
        });
      },
      { threshold: 0.5 }
    );
    document.querySelectorAll("[data-target]").forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
}

export default function LandingPage() {
  const { cursorRef, ringRef } = useCursorCustom();
  useRevealOnScroll();
  useCounterAnimation();

  return (
    <div className="landing-page">
      <div ref={cursorRef} className="cursor-dot" />
      <div ref={ringRef} className="cursor-ring" />

      {/* NAV */}
      <nav className="landing-nav">
        <div className="landing-logo">
          <svg width="28" height="28" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="16" cy="16" r="5" fill="#ff2d4a">
              <animate attributeName="opacity" values="1;0.5;1" dur="2.5s" repeatCount="indefinite"/>
            </circle>
            <circle cx="16" cy="16" r="9" stroke="#ff2d4a" strokeOpacity="0.3" strokeWidth="1" fill="none"/>
          </svg>
          SPECTER
        </div>
        <ul className="landing-nav-links">
          <li><a href="#how">How it works</a></li>
          <li><a href="#demo">Demo</a></li>
          <li><a href="#pricing">Pricing</a></li>
        </ul>
        <Link href="/dashboard" className="landing-nav-cta">
          Dashboard
        </Link>
      </nav>

      {/* HERO */}
      <section className="landing-hero">
        <div className="hero-grid" />
        <div className="hero-glow" />
        <div className="hero-badge">AI Package Security</div>
        <h1 className="hero-title">
          See what<br />others<br />
          <span className="hero-highlight">can&apos;t.</span>
        </h1>
        <p className="hero-sub">
          LLMs hallucinate package names. Attackers register them.
          Specter detects poisoned dependencies before they reach
          production — in your IDE, your CI, your pipeline.
        </p>
        <div className="hero-actions">
          <Link href="/dashboard" className="btn-landing-primary">
            Open Dashboard
          </Link>
          <a href="https://github.com" className="btn-landing-ghost">
            View on GitHub
          </a>
        </div>
      </section>

      {/* TICKER */}
      <div className="ticker-wrap">
        <div className="ticker">
          {[
            "npm ecosystem", "PyPI ecosystem", "2.5M+ packages monitored",
            "Real-time scanning", "VS Code plugin", "GitHub Actions",
            "REST API", "AI hallucination detection", "Supply chain security",
            "npm ecosystem", "PyPI ecosystem", "2.5M+ packages monitored",
            "Real-time scanning", "VS Code plugin", "GitHub Actions",
            "REST API", "AI hallucination detection", "Supply chain security",
          ].map((t, i) => (
            <div key={i} className="ticker-item">
              {t}<span className="ticker-sep">//</span>
            </div>
          ))}
        </div>
      </div>

      {/* STATS */}
      <div className="landing-stats reveal">
        <div className="landing-stat">
          <div className="stat-num" data-target="200000">0</div>
          <div className="stat-label">Hallucinated pkg names catalogued</div>
        </div>
        <div className="landing-stat">
          <div className="stat-num" data-target="20">0</div>
          <div className="stat-label">% of AI code suggestions affected</div>
        </div>
        <div className="landing-stat">
          <div className="stat-num">&lt; 200ms</div>
          <div className="stat-label">Scan latency per dependency</div>
        </div>
        <div className="landing-stat">
          <div className="stat-num">3M+</div>
          <div className="stat-label">Packages indexed across ecosystems</div>
        </div>
      </div>

      {/* HOW IT WORKS */}
      <section className="landing-section" id="how">
        <div className="section-tag">How it works</div>
        <h2 className="section-title reveal">
          Three layers of protection before a single bad package ships
        </h2>
        <div className="landing-steps">
          {[
            { num: "01", icon: "\u{1F441}", title: "Detect", desc: "Specter continuously ingests npm and PyPI, running 40+ risk signals on every new package — age, maintainer history, typosquatting score, install script behavior, and more." },
            { num: "02", icon: "\u26A1", title: "Classify", desc: "Our Wings ML engine scores every package 0\u20131 in real time. Borderline packages get semantic LLM analysis. The model gets smarter with every scan across all customers." },
            { num: "03", icon: "\u{1F6E1}\uFE0F", title: "Block", desc: "Packages flagged above your threshold get highlighted in your IDE, blocked in CI, and logged for compliance — before any code reaches production." },
          ].map((s, i) => (
            <div key={i} className="landing-step reveal" style={{ transitionDelay: `${i * 0.1}s` }}>
              <div className="step-num">{s.num}</div>
              <span className="step-icon">{s.icon}</span>
              <h3>{s.title}</h3>
              <p>{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* TERMINAL DEMO */}
      <div className="demo-section" id="demo">
        <div className="demo-copy reveal">
          <div className="section-tag">Terminal demo</div>
          <h2 className="section-title">Catches what<br />audit misses</h2>
          <p className="demo-desc">
            Traditional scanners only flag known CVEs. Specter detects
            malicious behavior in packages with zero history — exactly
            the window attackers exploit.
          </p>
          <ul className="feature-list">
            <li>Works on any import statement as you type in VS Code</li>
            <li>Scans your entire requirements.txt or package.json instantly</li>
            <li>Blocks CI pipelines when risk threshold is exceeded</li>
            <li>Explains <em>why</em> a package is flagged, not just that it is</li>
          </ul>
        </div>
        <div className="terminal reveal scan-wrap">
          <div className="scan-line" />
          <div className="terminal-bar">
            <span className="dot dot-r" />
            <span className="dot dot-y" />
            <span className="dot dot-g" />
            <span className="terminal-title">specter scan — project dependencies</span>
          </div>
          <div className="terminal-body">
            <div className="t-comment"># Scanning package.json + requirements.txt</div>
            <br />
            <div className="t-cmd">specter scan --threshold 0.5</div>
            <br />
            <div className="t-muted">&rarr; Indexing 47 dependencies...</div>
            <div className="t-muted">&rarr; Running Wings ML engine...</div>
            <div className="t-muted">&rarr; Checking 3,100,000 package signatures...</div>
            <br />
            <div className="t-out">&check; lodash@4.17.21 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; score: 0.02 &nbsp;[SAFE]</div>
            <div className="t-out">&check; react@18.2.0 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; score: 0.01 &nbsp;[SAFE]</div>
            <div className="t-out">&check; axios@1.6.0 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; score: 0.03 &nbsp;[SAFE]</div>
            <div className="t-warn">&loz; crypo@1.0.0 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; score: 0.71 &nbsp;[REVIEW]</div>
            <div className="t-muted">&nbsp;&nbsp;&lfloor; typosquatting: 0.94 (&rarr; crypto)</div>
            <div className="t-muted">&nbsp;&nbsp;&lfloor; published: 3 days ago, 0 stars</div>
            <div className="t-err">&times; reqeusts@2.28.0 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; score: 0.94 &nbsp;[BLOCKED]</div>
            <div className="t-muted">&nbsp;&nbsp;&lfloor; typosquatting: 0.97 (&rarr; requests)</div>
            <div className="t-muted">&nbsp;&nbsp;&lfloor; postinstall: network egress detected</div>
            <div className="t-muted">&nbsp;&nbsp;&lfloor; LLM analysis: likely malicious</div>
            <br />
            <div className="t-err">&times; 1 blocked / &loz; 1 flagged / &check; 45 clean</div>
            <div className="t-info">&rarr; Report: specter.dev/report/a3f9b2c</div>
          </div>
        </div>
      </div>

      {/* PRICING */}
      <section className="landing-section" id="pricing">
        <div className="section-tag reveal">Pricing</div>
        <h2 className="section-title reveal">Start free.<br />Scale when it matters.</h2>
        <div className="landing-plans">
          {[
            {
              label: "Free", name: "Developer", price: "$0", period: "forever",
              featured: false,
              features: [
                { text: "VS Code plugin", active: true },
                { text: "500 scans / month", active: true },
                { text: "npm + PyPI coverage", active: true },
                { text: "GitHub Action", active: false },
                { text: "API access", active: false },
                { text: "Compliance reports", active: false },
              ],
              btn: "Install Plugin", btnStyle: "outline" as const,
            },
            {
              label: "Most Popular", name: "Pro", price: "$49", period: "per month, billed annually",
              featured: true,
              features: [
                { text: "Everything in Free", active: true },
                { text: "Unlimited scans", active: true },
                { text: "GitHub Actions CI block", active: true },
                { text: "Full API access", active: true },
                { text: "LLM deep analysis", active: true },
                { text: "Compliance reports", active: false },
              ],
              btn: "Start Free Trial", btnStyle: "solid" as const,
            },
            {
              label: "Enterprise", name: "Team", price: "Custom", period: "volume pricing available",
              featured: false,
              features: [
                { text: "Everything in Pro", active: true },
                { text: "SOC2 / LGPD reports", active: true },
                { text: "Custom risk policies", active: true },
                { text: "SIEM integration", active: true },
                { text: "SLA + dedicated support", active: true },
                { text: "On-prem deployment", active: true },
              ],
              btn: "Talk to Sales", btnStyle: "outline" as const,
            },
          ].map((plan, i) => (
            <div
              key={i}
              className={`landing-plan reveal ${plan.featured ? "plan-featured" : ""}`}
              style={{ transitionDelay: `${i * 0.1}s` }}
            >
              <div className="plan-label">{plan.label}</div>
              <div className="plan-name">{plan.name}</div>
              <div className="plan-price">
                {plan.price}
                {plan.price.startsWith("$") && plan.price !== "$0" && (
                  <span>/dev</span>
                )}
              </div>
              <div className="plan-period">{plan.period}</div>
              <ul className="plan-features">
                {plan.features.map((f, j) => (
                  <li key={j} className={f.active ? "active" : ""}>{f.text}</li>
                ))}
              </ul>
              <button
                className={`plan-btn ${plan.btnStyle === "solid" ? "plan-btn-solid" : "plan-btn-outline"}`}
              >
                {plan.btn}
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="cta-section">
        <div className="cta-glow" />
        <div className="cta-eyebrow">Get started today</div>
        <h2 className="cta-title reveal">
          Your next deploy<br />shouldn&apos;t be a gamble.
        </h2>
        <p className="cta-sub reveal">
          Install the VS Code plugin in 30 seconds. No account required.
        </p>
        <div className="hero-actions" style={{ justifyContent: "center" }}>
          <Link href="/dashboard" className="btn-landing-primary">
            Open Dashboard
          </Link>
          <a href="#" className="btn-landing-ghost">Read the Docs</a>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="landing-footer">
        <div className="footer-copy">
          &copy; 2025 Specter Security, Inc. — See what others can&apos;t.
        </div>
        <div className="footer-links">
          <a href="#">Docs</a>
          <a href="#">GitHub</a>
          <a href="#">Security</a>
          <a href="#">Privacy</a>
        </div>
      </footer>
    </div>
  );
}
