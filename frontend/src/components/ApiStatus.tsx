import { useEffect, useState } from 'react'

import { getHealth } from '../api/health'

type ApiState = 'checking' | 'online' | 'offline'

export function ApiStatus() {
  const [state, setState] = useState<ApiState>('checking')

  useEffect(() => {
    const controller = new AbortController()

    getHealth(controller.signal)
      .then(() => setState('online'))
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
          setState('offline')
        }
      })

    return () => controller.abort()
  }, [])

  return (
    <div className={`api-status api-status--${state}`} role="status">
      <span className="api-status__dot" aria-hidden="true" />
      API {state}
    </div>
  )
}
