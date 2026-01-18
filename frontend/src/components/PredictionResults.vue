<template>
  <div class="space-y-8 w-full">
    <!-- Main Prediction Card -->
    <div class="hero-card">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-2xl font-bold text-white uppercase tracking-tight">{{ $t('results.title') }}</h3>
      </div>

      <div class="text-center py-4">
      <div class="text-5xl md:text-6xl font-bold mb-2 font-mono tracking-tight text-slate-900">
        {{ prediction.total_time_formatted }}
      </div>

        <div class="text-slate-400 text-sm font-mono">
          {{ $t('results.confidence_interval') }}: <span class="text-emerald-300">{{ prediction.confidence_interval.lower_formatted }}</span> -
          <span class="text-emerald-300">{{ prediction.confidence_interval.upper_formatted }}</span>
        </div>

        <!-- Hybrid System Info (Translated) -->
        <div v-if="prediction.metadata" class="mt-4 text-slate-500 text-xs max-w-lg mx-auto border-t border-slate-800 pt-3">
          {{ $t(`prediction.descriptions.${prediction.metadata.tier}`, { count: prediction.metadata.activities_used }) }}
        </div>
      </div>

      <div class="grid grid-cols-3 gap-4 mt-6 pt-6 border-t border-slate-200">
        <div class="text-center rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
          <div class="text-2xl font-bold font-mono text-emerald-600">{{ prediction.statistics.total_distance_km.toFixed(2) }}</div>
          <div class="text-slate-500 text-xs uppercase tracking-wider">{{ $t('results.km') }}</div>
        </div>
        <div class="text-center rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
          <div class="text-2xl font-bold font-mono text-emerald-600">{{ Math.round(prediction.statistics.total_elevation_gain_m) }}</div>
          <div class="text-slate-500 text-xs uppercase tracking-wider">{{ $t('results.m_gain') }}</div>
        </div>
        <div class="text-center rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
          <div class="text-2xl font-bold font-mono text-emerald-600">{{ formatPace(prediction.statistics.flat_pace_min_per_km) }}</div>
          <div class="text-slate-500 text-xs uppercase tracking-wider">{{ $t('results.flat_pace') }}</div>
        </div>
      </div>
    </div>

    <!-- Map Visualization -->
    <div class="card p-1 h-[500px] relative overflow-hidden bg-slate-100">
      <MapView
        v-if="gpxStore.points.length"
        :points="gpxStore.points"
        :annotations="predictionStore.annotations"
      />
      <div v-else class="flex items-center justify-center h-full text-slate-500">
        Loading map data...
      </div>
    </div>

    <!-- Elevation & Pace Profile -->
    <div class="card p-4 sm:p-6">
      <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-6">
        <div>
          <h3 class="text-xl font-bold text-slate-900">{{ $t('results.elevation_pace_title') }}</h3>
          <p class="text-xs text-slate-500 uppercase tracking-wide mt-1">{{ $t('results.interactive_analysis') }}</p>
        </div>

        <!-- Split Level Control -->
        <div class="flex flex-col sm:flex-row sm:items-center gap-3 w-full sm:w-auto">
          <button v-if="isProfileZoomed" class="btn btn-outline text-xs py-1.5 w-full sm:w-auto" type="button" @click="resetProfileZoom">
            {{ $t('results.reset_zoom') }}
          </button>
          
          <div class="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 w-full sm:w-auto">
            <span class="text-[10px] font-bold uppercase tracking-wider text-slate-400">{{ $t('results.granularity') }}</span>
            <input
              v-model.number="localSplitLevel"
              @input="regroupSegments"
              type="range"
              min="1"
              :max="maxValidLevel"
              step="1"
              class="w-full sm:w-24 h-1.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-emerald-600"
            />
            <span class="text-sm font-bold text-slate-700 font-mono w-4 text-center">{{ localSplitLevel }}</span>
          </div>
          <button
            v-if="prediction.prediction_id"
            @click="exportVirtualPartner"
            class="btn btn-primary text-xs w-full sm:w-auto"
          >
            <span>🏃</span> {{ $t('results.buttons.export_vp') }}
          </button>
        </div>
      </div>
      <div v-if="isMobile && Number.isFinite(pendingAnnotationDistance)" class="mb-4 flex items-center justify-between gap-3 rounded-lg border border-emerald-100 bg-emerald-50/80 px-3 py-2 text-xs text-emerald-900">
        <span class="font-semibold">{{ $t('results.add_annotation_at', { distance: pendingAnnotationDistance.toFixed(2) }) }}</span>
        <button class="btn btn-primary text-xs px-3 py-1.5" type="button" @click="openMobileAnnotation">
          ✏️ {{ $t('results.add_annotation') }}
        </button>
      </div>

      <ElevationPaceProfile
        ref="elevationProfileRef"
        v-if="gpxStore.points.length"
        :points="gpxStore.points"
        :segments="displaySegments"
        :raw-segments="rawSegments"
        :average-pace="prediction.statistics.flat_pace_min_per_km"
        :annotations="predictionStore.annotations"
        :selected-range="selectedRange"
        :tap-to-reveal="isMobile"
        :edit-label="$t('results.edit_annotation')"
        @click-chart="handleChartClick"
        @annotation-click="handleAnnotationClick"
        @range-selected="handleRangeSelected"
        @zoom-changed="handleZoomChanged"
      />
      <div v-else class="flex items-center justify-center h-[500px] text-slate-500">
        Loading profile data...
      </div>
    </div>

    <!-- Similar Activities -->
    <div v-if="similarActivities.length > 0" class="card p-6">
      <h3 class="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
         <span class="w-1.5 h-6 bg-sky-500 rounded-full"></span>
         {{ $t('results.similar_activities') }}
      </h3>

      <div class="grid sm:grid-cols-2 gap-4">
        <div
          v-for="activity in similarActivities"
          :key="activity.id"
          class="flex justify-between items-start rounded-xl border border-slate-100 bg-slate-50/50 p-4 hover:border-sky-200 hover:bg-sky-50 transition-colors cursor-default"
        >
          <div>
            <p class="font-bold text-slate-800 text-sm mb-1">{{ activity.name }}</p>
            <p class="text-xs text-slate-500 flex items-center gap-2">
              <span>{{ (activity.distance / 1000).toFixed(2) }} km</span>
              <span class="w-1 h-1 rounded-full bg-slate-300"></span>
              <span>{{ formatDate(activity.start_date) }}</span>
            </p>
          </div>
          <div class="text-right">
            <div class="font-bold font-mono text-slate-900">
              {{ formatTime(activity.moving_time) }}
            </div>
            <div class="text-[10px] uppercase tracking-wide text-slate-400">{{ $t('results.actual_time') }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Annotation Modal -->
    <AnnotationModal
      :show="showAnnotationModal"
      :distance-km="pendingAnnotationDistance"
      :predicted-time="pendingAnnotationPredictedTime"
      :anchor="annotationAnchor"
      :annotation="editingAnnotation"
      @close="closeAnnotationModal"
      @save="saveAnnotation"
      @delete="removeEditingAnnotation"
    />

  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useGpxStore } from '../stores/gpx'
import { usePredictionStore } from '../stores/prediction'
import { useI18n } from 'vue-i18n'
import MapView from './MapView.vue'
import ElevationPaceProfile from './ElevationPaceProfile.vue'
import AnnotationModal from './AnnotationModal.vue'
import api from '../services/api'

const gpxStore = useGpxStore()
const predictionStore = usePredictionStore()
const { locale, t } = useI18n()

const props = defineProps({
  prediction: {
    type: Object,
    required: true
  },
  similarActivities: {
    type: Array,
    default: () => []
  },
  selectedActivity: {
    type: Object,
    default: null
  }
})

const emit = defineEmits([])

const localSplitLevel = ref(predictionStore.splitLevel)
const displaySegments = ref([])
const rawSegments = ref([])
const elevationProfileRef = ref(null)
const isProfileZoomed = ref(false)
const showAnnotationModal = ref(false)
const pendingAnnotationDistance = ref(null)
const pendingAnnotationPredictedTime = ref(null)
const annotationAnchor = ref(null)
const selectedRange = ref(null)
const selectedRangeTime = ref(null)
const cachedSegmentsByLevel = ref({}) // Cache for all 5 levels
const maxValidLevel = ref(5) // Highest level that doesn't exceed MAX_SEGMENTS
const isMobile = ref(false)
let mobileMql = null
let mobileMqlHandler = null
const segmentTimeline = ref([])
const segmentEnds = ref([])
const editingAnnotation = ref(null)
const prevBodyOverflow = ref('')
const prevBodyPaddingRight = ref('')

// Group segments by gradient changes
const getSplitGrade = (segment) => {
  if (typeof segment._smoothed_grade === 'number') return segment._smoothed_grade
  return segment.grade
}

const smoothSegmentGrades = (segments, windowMeters) => {
  if (!segments || segments.length === 0) return []

  const halfWindow = windowMeters / 2
  const centers = segments.map(seg => seg.distance_m + seg.length_m / 2)

  return segments.map((seg, index) => {
    const center = centers[index]
    const windowStart = center - halfWindow
    const windowEnd = center + halfWindow

    let weightedSum = 0
    let weightTotal = 0

    for (let i = 0; i < segments.length; i++) {
      const segCenter = centers[i]
      if (segCenter < windowStart || segCenter > windowEnd) continue

      const weight = segments[i].length_m || 0
      weightedSum += (segments[i].grade * weight)
      weightTotal += weight
    }

    const smoothedGrade = weightTotal > 0 ? weightedSum / weightTotal : seg.grade

    return {
      ...seg,
      _smoothed_grade: smoothedGrade
    }
  })
}

const groupSegmentsByGradient = (segments, gradientThreshold, maxSegmentLength, signChangeMinGrade) => {
  if (!segments || segments.length === 0) return []

  const grouped = []
  let currentGroup = [segments[0]]
  let currentStart = segments[0].distance_m

  for (let i = 1; i < segments.length; i++) {
    const prev = segments[i - 1]
    const curr = segments[i]

    const prevGrade = getSplitGrade(prev) * 100
    const currGrade = getSplitGrade(curr) * 100

    const gradeChange = Math.abs(currGrade - prevGrade)
    const signChange = (prevGrade * currGrade < 0) &&
                       (Math.abs(prevGrade) > signChangeMinGrade || Math.abs(currGrade) > signChangeMinGrade)
    const currentLength = curr.distance_m - currentStart

    // Different sensitivity for uphill vs downhill
    let effectiveThreshold = gradientThreshold

    // If both segments are uphill, be less sensitive (higher threshold)
    if (prevGrade > 0 && currGrade > 0) {
      effectiveThreshold = gradientThreshold * 1.2
    }
    // If both segments are downhill, be more sensitive (lower threshold)
    else if (prevGrade < -1 && currGrade < -1) {
      effectiveThreshold = gradientThreshold * 0.8
    }

    if (gradeChange > effectiveThreshold || signChange || currentLength > maxSegmentLength) {
      grouped.push(currentGroup)
      currentGroup = [curr]
      currentStart = curr.distance_m
    } else {
      currentGroup.push(curr)
    }
  }

  if (currentGroup.length > 0) {
    grouped.push(currentGroup)
  }

  return grouped
}

// Format grouped segments for display
const formatGroupedSegments = (segmentGroups) => {
  const mlSegments = []
  let cumulativeTime = 0

  segmentGroups.forEach((group, index) => {
    const groupTime = group.reduce((sum, s) => sum + s.time_s, 0)
    const groupDist = group.reduce((sum, s) => sum + s.length_m, 0)
    const avgGrade = group.reduce((sum, s) => sum + s.grade, 0) / group.length
    const avgPace = groupTime / (groupDist / 1000) / 60

    cumulativeTime += groupTime
    const startKm = group[0].distance_m / 1000
    const endKm = (group[group.length - 1].distance_m + group[group.length - 1].length_m) / 1000

    const hours = Math.floor(cumulativeTime / 3600)
    const mins = Math.floor((cumulativeTime % 3600) / 60)
    const secs = Math.floor(cumulativeTime % 60)

    let terrain
    if (avgGrade > 0.08) terrain = "Steep Climb"
    else if (avgGrade > 0.03) terrain = "Climb"
    else if (avgGrade > -0.03) terrain = "Flat"
    else if (avgGrade > -0.08) terrain = "Descent"
    else terrain = "Steep Descent"

    mlSegments.push({
      split_number: index + 1,
      segment_km: Math.floor(endKm),
      start_km: parseFloat(startKm.toFixed(2)),
      end_km: parseFloat(endKm.toFixed(2)),
      avg_grade_percent: parseFloat((avgGrade * 100).toFixed(1)),
      avg_pace_min_per_km: parseFloat(avgPace.toFixed(2)),
      time_formatted: `${hours}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`,
      terrain: terrain,
      distance_m: parseFloat(groupDist.toFixed(1))
    })
  })

  return mlSegments
}

// Thresholds configuration
const thresholds = {
  1: { gradient: 20.0, signChange: 20.0, maxLength: 20000, smoothWindow: 800 }, // Very coarse
  2: { gradient: 12.0, signChange: 12.0, maxLength: 15000, smoothWindow: 500 },  // Coarse
  3: { gradient: 6.0, signChange: 6.0, maxLength: 10000, smoothWindow: 300 },    // Medium
  4: { gradient: 3.0, signChange: 3.0, maxLength: 6000, smoothWindow: 200 },     // Fine
  5: { gradient: 1.0, signChange: 1.0, maxLength: 3000, smoothWindow: 150 }      // Very fine
}

const MAX_SEGMENTS = 200

// Compute segments for a specific level
const computeSegmentsForLevel = (rawSegmentsData, level) => {
  const config = thresholds[level] || thresholds[3]
  const smoothedSegments = smoothSegmentGrades(rawSegmentsData, config.smoothWindow)
  const segmentGroups = groupSegmentsByGradient(
    smoothedSegments,
    config.gradient,
    config.maxLength,
    config.signChange
  )
  return formatGroupedSegments(segmentGroups)
}

// Precompute all levels and cache them
const precomputeAllLevels = () => {
  const rawSegmentsData = props.prediction.raw_segments
  if (!rawSegmentsData || rawSegmentsData.length === 0) {
    displaySegments.value = props.prediction.segments
    rawSegments.value = []
    return
  }

  rawSegments.value = rawSegmentsData
  console.log('Precomputing all segment levels...')

  // Compute all 5 levels and track max valid level
  let highestValid = 1
  for (let level = 1; level <= 5; level++) {
    const segments = computeSegmentsForLevel(rawSegmentsData, level)
    cachedSegmentsByLevel.value[level] = segments
    console.log(`Level ${level}: ${segments.length} segments`)

    if (segments.length <= MAX_SEGMENTS) {
      highestValid = level
    }
  }

  maxValidLevel.value = highestValid
  console.log(`Max valid level: ${highestValid}`)

  // Clamp initial level to max valid
  if (localSplitLevel.value > maxValidLevel.value) {
    localSplitLevel.value = maxValidLevel.value
  }

  // Set initial display
  regroupSegments()
}

// Regroup segments based on split level (now just switches cached versions)
const regroupSegments = () => {
  const rawSegmentsData = props.prediction.raw_segments
  if (!rawSegmentsData || rawSegmentsData.length === 0) {
    displaySegments.value = props.prediction.segments
    return
  }

  // Simply use cached segments for current level (already validated to be <= MAX_SEGMENTS)
  const cached = cachedSegmentsByLevel.value[localSplitLevel.value]
  if (cached) {
    displaySegments.value = cached
  } else {
    // Fallback to level 1
    displaySegments.value = cachedSegmentsByLevel.value[1] || []
  }
}

const resetProfileZoom = () => {
  elevationProfileRef.value?.resetZoom()
  elevationProfileRef.value?.clearClickMarker()
  isProfileZoomed.value = false
}

const handleZoomChanged = (isZoomed) => {
  isProfileZoomed.value = isZoomed
  elevationProfileRef.value?.clearClickMarker()
}

const formatSecondsToHms = (totalTime) => {
  const h = Math.floor(totalTime / 3600)
  const m = Math.floor((totalTime % 3600) / 60)
  const s = Math.floor(totalTime % 60)
  return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

const buildSegmentTimeline = (segments) => {
  const fallbackPace = props.prediction?.statistics?.flat_pace_min_per_km
  const ordered = [...(segments || [])].sort((a, b) => {
    const aStart = a.start_km ?? 0
    const bStart = b.start_km ?? 0
    return aStart - bStart
  })
  const timeline = []
  let cumTime = 0

  ordered.forEach(seg => {
    const startKm = seg.start_km ?? 0
    const endKm = seg.end_km ?? seg.segment_km ?? 0
    if (!Number.isFinite(startKm) || !Number.isFinite(endKm) || endKm <= startKm) {
      return
    }
    const pace = Number.isFinite(seg.avg_pace_min_per_km)
      ? seg.avg_pace_min_per_km
      : (Number.isFinite(fallbackPace) ? fallbackPace : null)
    if (!Number.isFinite(pace)) return

    const segTime = pace * (endKm - startKm) * 60
    const entry = {
      startKm,
      endKm,
      pace,
      cumTimeStart: cumTime,
      cumTimeEnd: cumTime + segTime
    }
    cumTime = entry.cumTimeEnd
    timeline.push(entry)
  })

  segmentTimeline.value = timeline
  segmentEnds.value = timeline.map(seg => seg.endKm)
}

const handleChartClick = ({ distanceKm, screenX, screenY }) => {
  editingAnnotation.value = null
  pendingAnnotationDistance.value = distanceKm
  pendingAnnotationPredictedTime.value = calculateTimeToDistance(distanceKm)
  annotationAnchor.value = Number.isFinite(screenX) && Number.isFinite(screenY)
    ? { x: screenX, y: screenY }
    : null
  if (isMobile.value) {
    return
  }
  elevationProfileRef.value?.hideTooltip()
  showAnnotationModal.value = true
}

const openMobileAnnotation = () => {
  if (!Number.isFinite(pendingAnnotationDistance.value)) return
  elevationProfileRef.value?.hideTooltip()
  showAnnotationModal.value = true
}

const handleAnnotationClick = ({ annotation, screenX, screenY }) => {
  if (!annotation) return
  editingAnnotation.value = annotation
  pendingAnnotationDistance.value = annotation.distance_km
  pendingAnnotationPredictedTime.value = calculateTimeToDistance(annotation.distance_km)
  annotationAnchor.value = Number.isFinite(screenX) && Number.isFinite(screenY)
    ? { x: screenX, y: screenY }
    : null
  elevationProfileRef.value?.hideTooltip()
  showAnnotationModal.value = true
}

const closeAnnotationModal = () => {
  showAnnotationModal.value = false
  elevationProfileRef.value?.clearClickMarker()
  editingAnnotation.value = null
}

const calculateTimeToDistance = (targetKm) => {
  if (!Number.isFinite(targetKm) || segmentTimeline.value.length === 0) {
    return formatSecondsToHms(0)
  }

  let low = 0
  let high = segmentEnds.value.length - 1
  let idx = segmentEnds.value.length - 1

  while (low <= high) {
    const mid = Math.floor((low + high) / 2)
    if (targetKm <= segmentEnds.value[mid]) {
      idx = mid
      high = mid - 1
    } else {
      low = mid + 1
    }
  }

  const seg = segmentTimeline.value[idx]
  if (!seg) return formatSecondsToHms(0)
  if (targetKm <= seg.startKm) {
    return formatSecondsToHms(seg.cumTimeStart)
  }

  const partialDist = Math.max(0, targetKm - seg.startKm)
  const totalTime = seg.cumTimeStart + (seg.pace * partialDist * 60)
  return formatSecondsToHms(totalTime)
}

const handleRangeSelected = (range) => {
  selectedRange.value = range
  if (range) {
    selectedRangeTime.value = calculateRangeTime(range.start_km, range.end_km)
  } else {
    selectedRangeTime.value = null
  }
}

const calculateRangeTime = (startKm, endKm) => {
  if (segmentTimeline.value.length === 0) {
    return formatSecondsToHms(0)
  }

  let totalTime = 0
  let low = 0
  let high = segmentEnds.value.length - 1
  let idx = segmentEnds.value.length - 1

  while (low <= high) {
    const mid = Math.floor((low + high) / 2)
    if (startKm <= segmentEnds.value[mid]) {
      idx = mid
      high = mid - 1
    } else {
      low = mid + 1
    }
  }

  for (let i = idx; i < segmentTimeline.value.length; i++) {
    const seg = segmentTimeline.value[i]
    if (seg.startKm >= endKm) break

    if (seg.endKm > startKm && seg.startKm < endKm) {
      const overlapStart = Math.max(seg.startKm, startKm)
      const overlapEnd = Math.min(seg.endKm, endKm)
      const overlapDist = overlapEnd - overlapStart
      if (overlapDist > 0) {
        totalTime += seg.pace * overlapDist * 60
      }
    }
  }

  return formatSecondsToHms(totalTime)
}

const saveAnnotation = (annotation) => {
  const targetDist = pendingAnnotationDistance.value * 1000
  let closest = null
  let minDiff = Infinity

  for (const point of gpxStore.points) {
    const diff = Math.abs(point.distance - targetDist)
    if (diff < minDiff) {
      minDiff = diff
      closest = point
    }
  }

  if (!closest) return

  if (editingAnnotation.value) {
    predictionStore.updateAnnotation(editingAnnotation.value.id, {
      ...annotation,
      distance_km: editingAnnotation.value.distance_km,
      lat: editingAnnotation.value.lat,
      lon: editingAnnotation.value.lon
    })
  } else {
    predictionStore.addAnnotation({
      ...annotation,
      lat: closest.lat,
      lon: closest.lon
    })
  }
}

const removeAnnotation = (annotationId) => {
  if (confirm('Remove this annotation?')) {
    predictionStore.removeAnnotation(annotationId)
  }
}

const removeEditingAnnotation = () => {
  if (!editingAnnotation.value) return
  predictionStore.removeAnnotation(editingAnnotation.value.id)
  closeAnnotationModal()
}

const saveAnnotationsToServer = async () => {
  if (!props.prediction.prediction_id) return
  try {
    await predictionStore.saveAnnotations(props.prediction.prediction_id)
    alert('Annotations saved successfully!')
  } catch (error) {
    alert('Failed to save annotations')
  }
}

onMounted(() => {
  precomputeAllLevels()

  if (props.prediction.prediction_id) {
    predictionStore.loadAnnotations(props.prediction.prediction_id)
  }

  if (typeof window !== 'undefined') {
    mobileMql = window.matchMedia('(max-width: 640px)')
    const update = (event) => {
      isMobile.value = event?.matches ?? mobileMql.matches
    }
    update()
    mobileMqlHandler = update
    if (mobileMql.addEventListener) {
      mobileMql.addEventListener('change', update)
    } else if (mobileMql.addListener) {
      mobileMql.addListener(update)
    }
  }
})

watch(displaySegments, (segments) => {
  buildSegmentTimeline(segments)
}, { immediate: true })

watch(showAnnotationModal, (isOpen) => {
  if (typeof document === 'undefined') return
  if (isOpen) {
    prevBodyOverflow.value = document.body.style.overflow
    prevBodyPaddingRight.value = document.body.style.paddingRight
    const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth
    document.body.style.overflow = 'hidden'
    if (scrollbarWidth > 0) {
      document.body.style.paddingRight = `${scrollbarWidth}px`
    }
  } else {
    document.body.style.overflow = prevBodyOverflow.value || ''
    document.body.style.paddingRight = prevBodyPaddingRight.value || ''
  }
})

onBeforeUnmount(() => {
  if (!mobileMql || !mobileMqlHandler) return
  if (mobileMql.removeEventListener) {
    mobileMql.removeEventListener('change', mobileMqlHandler)
  } else if (mobileMql.removeListener) {
    mobileMql.removeListener(mobileMqlHandler)
  }
})

const getGradeColor = (grade) => {
  if (grade > 5) return 'text-red-600 font-semibold'
  if (grade > 2) return 'text-orange-600'
  if (grade < -5) return 'text-green-600 font-semibold'
  if (grade < -2) return 'text-green-500'
  return 'text-gray-700'
}

const formatPace = (paceDecimal) => {
  const minutes = Math.floor(paceDecimal)
  const seconds = Math.round((paceDecimal - minutes) * 60)
  return `${minutes}m${seconds.toString().padStart(2, '0')}s/km`
}

const formatDate = (dateStr) => {
  const date = new Date(dateStr)
  return date.toLocaleDateString(locale.value, { month: 'short', day: 'numeric', year: 'numeric' })
}

const formatTime = (seconds) => {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

const exportVirtualPartner = async () => {
  if (!props.prediction.prediction_id) return
  
  try {
    const response = await api.get(`/prediction/${props.prediction.prediction_id}/export`, {
      responseType: 'blob'
    })
    
    const blob = new Blob([response.data], { type: 'application/gpx+xml' })
    const downloadUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = downloadUrl
    const filename = `virtual_partner_${props.prediction.prediction_id}.gpx`
    link.setAttribute('download', filename)
    document.body.appendChild(link)
    link.click()
    link.remove()
    
  } catch (error) {
    console.error('Failed to export GPX:', error)
    alert('Failed to export Virtual Partner file')
  }
}

const formatTier = (tier) => {
  return t(`prediction.tiers.${tier}`) || tier
}

const exportResults = () => {
  const text = `
Predicted Time: ${props.prediction.total_time_formatted}
Confidence: ${props.prediction.confidence_interval.lower_formatted} - ${props.prediction.confidence_interval.upper_formatted}

Statistics:
- Distance: ${props.prediction.statistics.total_distance_km.toFixed(2)} km
- Elevation Gain: ${Math.round(props.prediction.statistics.total_elevation_gain_m)} m
- Flat Pace: ${props.prediction.statistics.flat_pace_min_per_km.toFixed(2)} min/km

Segment Breakdown (Detail Level ${localSplitLevel.value}):
${displaySegments.value.map(s =>
  `Km ${s.segment_km || (s.start_km + '-' + s.end_km)}: ${s.time_formatted} (${s.avg_grade_percent.toFixed(1)}% grade, ${s.avg_pace_min_per_km.toFixed(2)} min/km)`
).join('\n')}
  `.trim()

  const blob = new Blob([text], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'prediction-results.txt'
  a.click()
  URL.revokeObjectURL(url)
}
</script>
