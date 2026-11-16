import { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { refreshSavedItems, saveItem, unsaveItem, selectIsSaved } from '../store/savedItemsSlice.js'

export default function SaveItemButton({ type, id }) {
  const dispatch = useDispatch()
  const authenticated = useSelector(state => state.session.status === 'authenticated')
  const status = useSelector(state => state.savedItems.status)
  const error = useSelector(state => state.savedItems.error)
  const saved = useSelector(state => selectIsSaved(state, type, id))
  useEffect(() => { if (authenticated && status === 'idle') dispatch(refreshSavedItems()) }, [authenticated, status, dispatch])
  if (!authenticated) return null
  return <div>
    <button type="button" className="secondary-button" disabled={status === 'loading'}
      onClick={() => dispatch(saved ? unsaveItem(type, id) : saveItem(type, id))}>
      {saved ? 'Unsave' : 'Save for later'}
    </button>
    {error && <p role="alert" className="error-message">{error}</p>}
  </div>
}
