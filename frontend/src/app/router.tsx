import { createBrowserRouter } from 'react-router-dom'

import { LandingPage } from '../features/landing/LandingPage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <LandingPage />,
  },
])
