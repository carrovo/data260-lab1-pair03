import { useCallback, useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { authenticate, initializeSession, logoutSession, selectSession } from '../store/sessionSlice.js'
import AuthContext from './authContext'

export default function AuthProvider({ children }) {
  const dispatch = useDispatch()
  const session = useSelector(selectSession)
  useEffect(() => { dispatch(initializeSession()) }, [dispatch])
  const logout = useCallback(() => dispatch(logoutSession(session.generation)), [dispatch, session.generation])
  return <AuthContext.Provider value={{
    student: session.user,
    initializing: !session.initialized || session.status === 'restoring',
    isAuthenticated: session.status === 'authenticated',
    logout,
    signIn: credentials => dispatch(authenticate('loginStudent', credentials)),
    signUp: data => dispatch(authenticate('signupStudent', data)),
  }}>{children}</AuthContext.Provider>
}
