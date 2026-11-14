import * as student from '../api'
import { companyApi } from './companyApi.js'
import { createAppStore } from './createStore.js'

export const store = createAppStore({ student, company: companyApi })
