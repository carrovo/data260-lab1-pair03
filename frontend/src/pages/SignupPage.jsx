import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import useAuth from '../auth/useAuth'
import AuthShell from '../components/AuthShell'

const initialFormData = {
  full_name: '',
  email: '',
  city: '',
  password: '',
}

function SignupPage() {
  const [formData, setFormData] = useState(initialFormData)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const { signUp } = useAuth()
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
      const response = await signUp(formData)

      setFormData(initialFormData)
      navigate('/jobs', {
        replace: true,
        state: {
          successMessage: `Account created successfully for ${response.student.full_name}.`,
        },
      })
    } catch (requestError) {
      setError(requestError.message)
      setLoading(false)
    }
  }

  return (
    <AuthShell
      alternateText="Already have an account?"
      alternateLinkText="Sign in"
      alternateTo="/login"
      description="Create your profile and start connecting with employers."
      eyebrow="GET STARTED"
      title="Create a student account"
    >
      <form className="auth-form" onSubmit={handleSubmit}>
        <label htmlFor="full-name">Full name</label>
        <input
          id="full-name"
          name="full_name"
          type="text"
          value={formData.full_name}
          onChange={handleChange}
          autoComplete="name"
          placeholder="Your full name"
          maxLength="255"
          required
        />

        <label htmlFor="signup-email">Email</label>
        <input
          id="signup-email"
          name="email"
          type="email"
          value={formData.email}
          onChange={handleChange}
          autoComplete="email"
          placeholder="you@example.com"
          required
        />

        <label htmlFor="city">City</label>
        <input
          id="city"
          name="city"
          type="text"
          value={formData.city}
          onChange={handleChange}
          autoComplete="address-level2"
          placeholder="San Jose"
          maxLength="100"
          required
        />

        <label htmlFor="signup-password">Password</label>
        <input
          id="signup-password"
          name="password"
          type="password"
          value={formData.password}
          onChange={handleChange}
          autoComplete="new-password"
          placeholder="At least 8 characters"
          minLength="8"
          required
        />

        <button className="auth-submit-button" type="submit" disabled={loading}>
          {loading ? 'Creating account...' : 'Create account'}
        </button>
        {error && <p className="error-message">{error}</p>}
      </form>
    </AuthShell>
  )
}

export default SignupPage
