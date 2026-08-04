import { Link } from 'react-router-dom'

export function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="auth-page">
      <section className="auth-card">
        <Link className="wordmark auth-card__brand" to="/" aria-label="KeptIt home">
          KeptIt<span aria-hidden="true">.</span>
        </Link>
        {children}
      </section>
    </main>
  )
}
