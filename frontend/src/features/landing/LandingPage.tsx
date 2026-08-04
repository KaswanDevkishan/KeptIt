import { Link } from 'react-router-dom'

import { ApiStatus } from '../../components/ApiStatus'

export function LandingPage() {
  return (
    <div className="site-shell">
      <header className="site-header">
        <Link className="wordmark" to="/" aria-label="KeptIt home">
          KeptIt<span aria-hidden="true">.</span>
        </Link>
        <nav aria-label="Primary navigation">
          <a className="text-link" href="#how-it-works">
            How it works
          </a>
          <button className="button button--compact button--quiet" type="button">
            Sign in
          </button>
        </nav>
      </header>

      <main>
        <section className="hero" aria-labelledby="hero-title">
          <div className="eyebrow">Your memory for the internet</div>
          <h1 id="hero-title">Never lose anything interesting on the internet again.</h1>
          <p className="hero__summary">
            KeptIt brings the useful, inspiring, and delightful links you discover into one calm,
            searchable place—along with the context that made them worth keeping.
          </p>
          <div className="hero__actions">
            <button className="button button--primary" type="button">
              Get started
            </button>
            <button className="button button--secondary" type="button">
              Sign in
            </button>
          </div>
        </section>

        <section className="value-card" id="how-it-works" aria-labelledby="value-title">
          <p className="value-card__number">01</p>
          <div>
            <h2 id="value-title">Keep the link. Remember the reason.</h2>
            <p>
              Build a private library across articles, videos, recipes, repositories, and the wider
              web. Organize it your way and find it when it matters.
            </p>
          </div>
        </section>
      </main>

      <footer className="site-footer">
        <p>© {new Date().getFullYear()} KeptIt</p>
        <p>Made for curious minds.</p>
        {import.meta.env.DEV && <ApiStatus />}
      </footer>
    </div>
  )
}
