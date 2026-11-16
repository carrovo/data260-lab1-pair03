// Whitelist numeric metadata; never copy arbitrary model/server content into metrics.
const count = value => Number.isSafeInteger(value) && value >= 0 ? value : null
export function safeUsage(value) {
  if (!value || typeof value !== 'object') return null
  return {
    model_calls: count(value.model_calls), prompt_tokens: count(value.prompt_tokens),
    completion_tokens: count(value.completion_tokens), total_tokens: count(value.total_tokens),
    latest_context_tokens: count(value.latest_context_tokens), context_capacity: count(value.context_capacity) || null,
    context_percent: Number.isFinite(value.context_percent) && value.context_percent >= 0 ? value.context_percent : null,
    context_is_estimate: value.context_is_estimate === true,
    calls: (Array.isArray(value.calls) ? value.calls : []).slice(0, 16).map(call => ({
      index: count(call.index), prompt_tokens: count(call.prompt_tokens), completion_tokens: count(call.completion_tokens),
      source: ['ollama', 'synthetic'].includes(call.source) ? call.source : 'unknown',
      purpose: ['agent', 'compaction_measure_before', 'compaction_summary', 'compaction_measure_after'].includes(call.purpose) ? call.purpose : 'unknown',
    })),
  }
}

export function safeCompaction(value) {
  if (!value || !['compacted', 'not_needed', 'failed'].includes(value.status)) return null
  return { status: value.status, before_prompt_tokens: count(value.before_prompt_tokens),
    after_prompt_tokens: count(value.after_prompt_tokens), automatic: value.automatic === true,
    measurement_source: ['ollama', 'synthetic'].includes(value.measurement_source) ? value.measurement_source : 'unknown' }
}

export const contextWarning = usage => Number.isFinite(usage?.context_percent) && usage.context_percent > 70
  && Number.isSafeInteger(usage?.context_capacity) && usage.context_capacity > 0
  && Number.isSafeInteger(usage?.latest_context_tokens) && usage.latest_context_tokens >= 0
