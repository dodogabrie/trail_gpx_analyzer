<template>
  <div v-if="show" class="fixed inset-0 z-[9999] pointer-events-none">
    <div
      class="card w-full max-w-[320px] pointer-events-auto max-h-[90vh] overflow-y-auto shadow-2xl shadow-slate-900/10 border border-slate-200"
      :style="modalStyle"
    >
      <div class="flex items-center justify-between mb-3">
        <div>
          <h3 class="text-base font-bold text-slate-900">{{ isEditing ? 'Edit Annotation' : 'Add Annotation' }}</h3>
          <p class="text-[10px] text-slate-500 uppercase tracking-[0.2em]">Route marker</p>
        </div>
        <div class="flex items-center gap-2">
          <button
            v-if="isEditing"
            @click="$emit('delete')"
            class="btn btn-ghost text-base leading-none text-rose-600 hover:text-rose-700"
            title="Delete"
          >
            🗑
          </button>
          <button @click="$emit('close')" class="btn btn-ghost text-xl leading-none">&times;</button>
        </div>
      </div>

      <div class="mb-3">
        <label class="block text-[10px] font-semibold uppercase tracking-[0.2em] mb-1 text-slate-500">Location</label>
        <div class="flex items-baseline gap-3">
          <p class="text-slate-900 font-mono font-bold text-base">{{ displayDistance().toFixed(2) }} km</p>
          <span class="text-xs text-slate-500 font-mono">
            <span class="text-emerald-600">+{{ cumulativeElevation?.dPlus || 0 }}m</span>
            <span class="mx-1">/</span>
            <span class="text-rose-500">-{{ cumulativeElevation?.dMinus || 0 }}m</span>
          </span>
        </div>
      </div>

      <div v-if="predictedTime" class="mb-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2">
        <label class="block text-[10px] font-semibold uppercase tracking-[0.2em] mb-1 text-emerald-700">
          Predicted Time to Reach
        </label>
        <p class="text-emerald-900 font-mono font-bold text-base">{{ formatPredictedTime(predictedTime) }}</p>
      </div>

      <div class="mb-3">
        <label class="block text-[10px] font-semibold uppercase tracking-[0.2em] mb-2 text-slate-500">Type</label>
        <div class="flex flex-wrap gap-2">
          <label class="flex items-center gap-2 rounded-full border border-slate-200 bg-white hover:bg-slate-50 px-2.5 py-1.5 text-xs font-semibold text-slate-700 cursor-pointer transition-colors">
            <input type="radio" v-model="annotationType" value="aid_station" class="accent-emerald-600">
            <span>Aid Station</span>
          </label>
          <label class="flex items-center gap-2 rounded-full border border-slate-200 bg-white hover:bg-slate-50 px-2.5 py-1.5 text-xs font-semibold text-slate-700 cursor-pointer transition-colors">
            <input type="radio" v-model="annotationType" value="generic" class="accent-emerald-600">
            <span>Generic</span>
          </label>
        </div>
      </div>

      <button
        type="button"
        class="w-full btn btn-outline text-xs py-1.5 mb-3"
        @click="expanded = !expanded"
      >
        {{ expanded ? 'Hide details' : 'Add details' }}
      </button>

      <div v-if="expanded" class="mb-3 space-y-3">
        <div>
          <label class="block text-[10px] font-semibold uppercase tracking-[0.2em] mb-2 text-slate-500">Label</label>
          <input
            v-model="label"
            type="text"
            class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-colors text-sm"
            placeholder="Edit label text..."
          >
          <p class="text-[10px] text-slate-500 mt-1">Format: Text - HH:MM:SS (time is predicted arrival)</p>
        </div>
        <div>
          <label class="block text-[10px] font-semibold uppercase tracking-[0.2em] mb-2 text-slate-500">Stop Time</label>
          <div class="flex items-center gap-2">
            <input
              v-model.number="stopTimeSeconds"
              type="number"
              min="0"
              step="10"
              class="w-24 rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition-colors text-sm font-mono"
            >
            <span class="text-sm text-slate-500">seconds</span>
          </div>
          <p class="text-[10px] text-slate-500 mt-1">Time spent at this point (added to total predicted time)</p>
        </div>
      </div>

      <div class="flex gap-2 justify-end mt-4">
        <button @click="$emit('close')" class="btn btn-outline">
          Cancel
        </button>
        <button @click="save" class="btn btn-primary">
          {{ isEditing ? 'Save' : 'Add Annotation' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  show: Boolean,
  distanceKm: Number,
  predictedTime: String,
  cumulativeElevation: {
    type: Object,
    default: () => ({ dPlus: 0, dMinus: 0 })
  },
  anchor: {
    type: Object,
    default: null
  },
  annotation: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['close', 'save', 'delete'])

const annotationType = ref('aid_station')
const label = ref('')
const stopTimeSeconds = ref(30)
const expanded = ref(false)
const isEditing = computed(() => !!props.annotation?.id)
const displayDistance = () => (Number.isFinite(props.distanceKm) ? props.distanceKm : 0)
const formatPredictedTime = (timeStr) => {
  if (!timeStr) return ''
  const parts = timeStr.split(':')
  if (parts.length >= 2) {
    return `${parts[0]}:${parts[1]}`
  }
  return timeStr
}

const getDefaultLabel = (type) => {
  const time = formatPredictedTime(props.predictedTime)
  if (!time) return type === 'aid_station' ? 'AS' : 'G'
  return type === 'aid_station' ? `${time} - AS` : `${time} - G`
}

const modalStyle = computed(() => {
  const viewportWidth = typeof window !== 'undefined' ? window.innerWidth : 1024
  const viewportHeight = typeof window !== 'undefined' ? window.innerHeight : 768
  const padding = 16
  const modalWidth = 360
  const modalHeight = 400
  const gap = 32 // Gap between click point and modal

  if (!props.anchor || !Number.isFinite(props.anchor.x) || !Number.isFinite(props.anchor.y)) {
    return {
      position: 'fixed',
      right: `${padding}px`,
      top: '50%',
      transform: 'translateY(-50%)'
    }
  }

  const anchorX = props.anchor.x
  const anchorY = props.anchor.y
  const clickedOnRightSide = anchorX > viewportWidth / 2

  // Position modal next to click point, on opposite side to not cover marker
  const style = {
    position: 'fixed',
    top: '50%',
    transform: 'translateY(-50%)'
  }

  if (clickedOnRightSide) {
    // Click on right -> modal to the left of click point
    const left = Math.max(padding, anchorX - modalWidth - gap)
    style.left = `${left}px`
  } else {
    // Click on left -> modal to the right of click point
    const left = Math.min(viewportWidth - modalWidth - padding, anchorX + gap)
    style.left = `${left}px`
  }

  return style
})

watch(() => props.show, (show) => {
  if (show) {
    expanded.value = false
    if (isEditing.value) {
      annotationType.value = props.annotation.type || 'aid_station'
      label.value = props.annotation.label || ''
      stopTimeSeconds.value = props.annotation.stop_time_seconds ?? 30
    } else {
      annotationType.value = 'aid_station'
      label.value = getDefaultLabel('aid_station')
      stopTimeSeconds.value = 30
    }
  }
})

watch(annotationType, (newType) => {
  if (isEditing.value) return
  if (newType === 'aid_station') {
    label.value = getDefaultLabel('aid_station')
  } else if (newType === 'generic') {
    label.value = getDefaultLabel('generic')
  }
})

const save = () => {
  if (!label.value.trim()) {
    alert('Please enter a label')
    return
  }

  const annotation = {
    type: annotationType.value,
    distance_km: props.distanceKm,
    label: label.value.trim(),
    stop_time_seconds: Math.max(0, stopTimeSeconds.value || 0)
  }

  emit('save', annotation)
  emit('close')
}
</script>
