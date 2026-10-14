import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import useAuth from '../auth/useAuth'
import AuthShell from '../components/AuthShell'


const initialFormData = {
  email: '',
  password: '',
}

function LoginPage() {
  const [formData, setFormData] = useState(initialFormData)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const { signIn } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()

  function handleChange(event) {
    const { name, value } = event.target

    setFormData((currentData) => ({
      ...currentData,
      [name]: value,
    }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setLoading(true)
    setError('')

    try {
      const response = await signIn(formData)
      const returnLocation = location.state?.from
      const returnPath = returnLocation?.pathname
        ? `${returnLocation.pathname}${returnLocation.search || ''}`
        : '/jobs'

      navigate(returnPath, {
        replace: true,
        state: {
          successMessage: `Welcome back, ${response.student.full_name}.`,
        },
      })
    } catch (requestError) {
      setError(requestError.message)
      setLoading(false)
    }
  }

  return (
    <AuthShell
      alternateText="New to Handshake?"
      alternateLinkText="Create a student account"
      alternateTo="/signup"
      description="Access your applications, registrations, and saved session."
      eyebrow="WELCOME BACK"
      title="Sign in to your account"
    >
      <form className="auth-form" onSubmit={handleSubmit}>
        <label htmlFor="login-email">Email</label>
        <input
          id="login-email"
          name="email"
          type="email"
          value={formData.email}
          onChange={handleChange}
          autoComplete="email"
          placeholder="you@example.com"
          required
        />

        <label htmlFor="login-password">Password</label>
        <input
          id="login-password"
          name="password"
          type="password"
          value={formData.password}
          onChange={handleChange}
          autoComplete="current-password"
          placeholder="Enter your password"
          required
        />

        <button className="auth-submit-button" type="submit" disabled={loading}>
          {loading ? 'Logging in...' : 'Log in'}
        </button>
        {error && <p className="error-message">{error}</p>}
      </form>
    </AuthShell>
  )
}

export default LoginPage
