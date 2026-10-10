import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  fetchCurrentStudent,
  loginStudent,
  signupStudent,
} from '../api'
import AuthContext from './authContext'


const TOKEN_STORAGE_KEY = 'student_access_token'

function AuthProvider({ children }) {
  const [savedToken] = useState(() =>
    localStorage.getItem(TOKEN_STORAGE_KEY),
  )
  const [accessToken, setAccessToken] = useState(null)
  const [student, setStudent] = useState(null)
  const [initializing, setInitializing] = useState(Boolean(savedToken))

  useEffect(() => {
    if (!savedToken) {
      return undefined
    }

    let active = true

    async function restoreSession() {
      try {
        const currentStudent = await fetchCurrentStudent(savedToken)

        if (active) {
          setAccessToken(savedToken)
          setStudent(currentStudent)
        }
      } catch (requestError) {
        if (
          active &&
          (requestError.status === 401 || requestError.status === 403)
        ) {
          localStorage.removeItem(TOKEN_STORAGE_KEY)
        }
      } finally {
        if (active) {
          setInitializing(false)
        }
      }
    }

    restoreSession()

    return () => {
      active = false
    }
  }, [savedToken])

  const saveSession = useCallback((authResponse) => {
    localStorage.setItem(
      TOKEN_STORAGE_KEY,
      authResponse.access_token,
    )
    setAccessToken(authResponse.access_token)
    setStudent(authResponse.student)

    return authResponse
  }, [])

  const signIn = useCallback(
    async (credentials) => {
      const authResponse = await loginStudent(credentials)
      return saveSession(authResponse)
    },
    [saveSession],
  )

  const signUp = useCallback(
    async (studentData) => {
      const authResponse = await signupStudent(studentData)
      return saveSession(authResponse)
    },
    [saveSession],
  )

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_STORAGE_KEY)
    setAccessToken(null)
    setStudent(null)
  }, [])

  const contextValue = useMemo(
    () => ({
      accessToken,
      initializing,
      isAuthenticated: Boolean(accessToken && student),
      logout,
      signIn,
      signUp,
      student,
    }),
    [accessToken, initializing, logout, signIn, signUp, student],
  )

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  )
}

export default AuthProvider
