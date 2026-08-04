export const MIN_PASSWORD_LENGTH = 12
export const MAX_PASSWORD_LENGTH = 1024

export function validateEmail(email: string): string | undefined {
  if (!email.trim()) return 'Enter your email address.'
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) return 'Enter a valid email address.'
}

export function validatePassword(password: string, requireMinimum = true): string | undefined {
  if (!password) return 'Enter your password.'
  if (requireMinimum && password.length < MIN_PASSWORD_LENGTH)
    return `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`
  if (password.length > MAX_PASSWORD_LENGTH)
    return `Password must be no more than ${MAX_PASSWORD_LENGTH} characters.`
}
