<template>
  <div class="space-y-6">
    <!-- Main Prediction Card -->
    <div class="hero-card">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-2xl font-bold">Predicted Time</h3>

        <!-- Hybrid System Badge -->
        <div v-if="prediction.metadata" class="flex flex-col items-end gap-1">
          <span class="pill border-white/40 bg-white/20 text-white">
            {{ formatTier(prediction.metadata.tier) }}
          </span>
          <span class="text-xs text-white/70">
            {{ prediction.metadata.confidence }} confidence
          </span>
        </div>
      </div>

      <div class="text-center">
        <div class="text-5xl font-bold mb-2">
          {{ prediction.total_time_formatted }}
        </div>

        <div class="text-white/75 text-sm">
          Confidence interval: {{ prediction.confidence_interval.lower_formatted }} -
          {{ prediction.confidence_interval.upper_formatted }}
        </div>

        <!-- Hybrid System Info -->
        <div v-if="prediction.metadata" class="mt-3 text-white/70 text-xs">
          {{ prediction.metadata.description }}
        </div>
      </div>

      <div class="grid grid-cols-3 gap-4 mt-6 pt-6 border-t border-white/20">
        <div class="text-center rounded-xl border border-white/20 bg-white/10 px-4 py-3">
          <div class="text-2xl font-bold">{{ prediction.statistics.total_distance_km.toFixed(2) }}</div>
          <div class="text-white/75 text-sm">km</div>
        </div>
        <div class="text-center rounded-xl border border-white/20 bg-white/10 px-4 py-3">
          <div class="text-2xl font-bold">{{ Math.round(prediction.statistics.total_elevation_gain_m) }}</div>
          <div class="text-white/75 text-sm">m gain</div>
        </div>
        <div class="text-center rounded-xl border border-white/20 bg-white/10 px-4 py-3">
          <div class="text-2xl font-bold">{{ formatPace(prediction.statistics.flat_pace_min_per_km) }}</div>
          <div class="text-white/75 text-sm">flat pace</div>
        </div>
      </div>
    </div>

    <!-- Actions -->
    <div class="flex gap-2">
      <button
        @click="$emit('recalibrate')"
        class="btn btn-outline"
      >
        Recalibrate
      </button>
      <button
        @click="exportResults"
        class="btn btn-outline"
      >
        Export Text
      </button>
      <button
        v-if="prediction.prediction_id"
        @click="exportVirtualPartner"
        class="btn btn-primary"
      >
        <span>🏃</span> Export Virtual Partner (GPX)
      </button>
    </div>

    <!-- Annotations Section -->
    <div v-if="predictionStore.annotations.length > 0 || selectedRange" class="card">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-xl font-bold">Annotations & Selections</h3>
        <button
          v-if="predictionStore.annotationsDirty"
          @click="saveAnnotationsToServer"
          class="btn btn-primary"
        >
          <span>💾</span> Save Annotations
        </button>
      </div>

      <!-- Selected Range Display -->
      <div v-if="selectedRange" class="mb-4 rounded-xl border border-lime-200 bg-lime-50 p-4">
        <div class="flex items-center justify-between">
          <div>
            <span class="font-semibold text-lime-900">Selected Range:</span>
            <span class="ml-2 text-lime-700">
              {{ selectedRange.start_km.toFixed(2) }} km - {{ selectedRange.end_km.toFixed(2) }} km
            </span>
            <span class="ml-2 text-lime-600">
              ({{ (selectedRange.end_km - selectedRange.start_km).toFixed(2) }} km)
            </span>
          </div>
          <div class="text-right">
            <div class="text-sm text-lime-600">Predicted time for this segment:</div>
            <div class="text-2xl font-bold text-lime-900">{{ selectedRangeTime }}</div>
          </div>
        </div>
      </div>

      <!-- Annotations List -->
      <div v-if="predictionStore.annotations.length > 0" class="space-y-2">
        <div
          v-for="ann in predictionStore.annotations"
          :key="ann.id"
          class="flex items-center justify-between rounded-xl border p-3"
          :class="ann.type === 'aid_station' ? 'bg-emerald-50 border-emerald-200' : 'bg-sky-50 border-sky-200'"
        >
          <div class="flex-1">
            <div class="flex items-center gap-2">
              <span v-if="ann.type === 'aid_station'" class="text-2xl">🚰</span>
              <span v-else class="text-2xl">📍</span>
              <div>
                <div class="font-semibold" :class="ann.type === 'aid_station' ? 'text-emerald-900' : 'text-sky-900'">
                  {{ ann.label }}
                </div>
                <div class="text-sm" :class="ann.type === 'aid_station' ? 'text-emerald-600' : 'text-sky-600'">
                  {{ ann.distance_km.toFixed(2) }} km
                </div>
              </div>
            </div>
          </div>
          <button
            @click="removeAnnotation(ann.id)"
            class="btn btn-danger"
          >
            Remove
          </button>
        </div>
      </div>

      <div v-else class="text-slate-500 text-sm italic">
        Click on the elevation profile below to add annotations (aid stations or generic markers)
      </div>
    </div>

    <!-- Map Visualization -->
    <div class="card p-2 h-[500px] relative">
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
    <div class="card">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-xl font-bold">Elevation & Pace Profile</h3>

        <!-- Split Level Control -->
        <div class="flex items-center gap-3 rounded-full border border-slate-200 bg-white/70 px-4 py-2">
          <span class="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Detail</span>
          <span class="text-xs text-slate-500">Less</span>
          <input
            v-model.number="localSplitLevel"
            @input="regroupSegments"
            type="range"
            min="1"
            :max="maxValidLevel"
            step="1"
            class="w-32 h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-lime-500"
          />
          <span class="text-xs text-slate-500">More</span>
          <span class="text-base font-bold text-slate-900">{{ localSplitLevel }}</span>
          <span v-if="maxValidLevel < 5" class="text-xs text-slate-500">(max {{ maxValidLevel }})</span>
        </div>
      </div>

      <ElevationPaceProfile
        v-if="gpxStore.points.length"
        :points="gpxStore.points"
        :segments="displaySegments"
        :raw-segments="rawSegments"
        :average-pace="prediction.statistics.flat_pace_min_per_km"
        :annotations="predictionStore.annotations"
        :selected-range="selectedRange"
        @click-chart="handleChartClick"
        @range-selected="handleRangeSelected"
      />
      <div v-else class="flex items-center justify-center h-[500px] text-slate-500">
        Loading profile data...
      </div>
    </div>

    <!-- Similar Activities -->
    <div v-if="similarActivities.length > 0" class="card">
      <h3 class="text-xl font-bold mb-4">Similar Past Activities</h3>

      <div class="space-y-2">
        <div
          v-for="activity in similarActivities"
          :key="activity.id"
          class="flex justify-between items-center rounded-xl border border-slate-200 bg-slate-50 px-3 py-2"
        >
          <div>
            <p class="font-medium">{{ activity.name }}</p>
            <p class="text-sm text-slate-600">
              {{ (activity.distance / 1000).toFixed(2) }} km
              <span class="mx-2">•</span>
              {{ formatDate(activity.start_date) }}
            </p>
          </div>
          <div class="text-right">
            <div class="font-bold text-slate-900">
              {{ formatTime(activity.moving_time) }}
            </div>
            <div class="text-xs text-slate-500">actual time</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Annotation Modal -->
    <AnnotationModal
      :show="showAnnotationModal"
      :distance-km="pendingAnnotationDistance"
      :predicted-time="pendingAnnotationPredictedTime"
      @close="showAnnotationModal = false"
      @save="saveAnnotation"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useGpxStore } from '../stores/gpx'
import { usePredictionStore } from '../stores/prediction'
import MapView from './MapView.vue'
import ElevationPaceProfile from './ElevationPaceProfile.vue'
import AnnotationModal from './AnnotationModal.vue'
import api from '../services/api'

const gpxStore = useGpxStore()
const predictionStore = usePredictionStore()

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

const emit = defineEmits(['recalibrate'])

const localSplitLevel = ref(predictionStore.splitLevel)
const displaySegments = ref([])
const rawSegments = ref([])
const showAnnotationModal = ref(false)
const pendingAnnotationDistance = ref(0)
const pendingAnnotationPredictedTime = ref(null)
const selectedRange = ref(null)
const selectedRangeTime = ref(null)
const cachedSegmentsByLevel = ref({}) // Cache for all 5 levels
const maxValidLevel = ref(5) // Highest level that doesn't exceed MAX_SEGMENTS

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

const handleChartClick = ({ distanceKm }) => {
  pendingAnnotationDistance.value = distanceKm
  pendingAnnotationPredictedTime.value = calculateTimeToDistance(distanceKm)
  showAnnotationModal.value = true
}

const calculateTimeToDistance = (targetKm) => {
  let totalTime = 0

  for (const seg of displaySegments.value) {
    const segStart = seg.start_km || 0
    const segEnd = seg.end_km || seg.segment_km || 0

    if (segStart >= targetKm) {
      break
    }

    if (segEnd <= targetKm) {
      // Entire segment is before target
      const segDist = segEnd - segStart
      const segTime = seg.avg_pace_min_per_km * segDist * 60
      totalTime += segTime
    } else {
      // Target is inside this segment
      const partialDist = targetKm - segStart
      const segTime = seg.avg_pace_min_per_km * partialDist * 60
      totalTime += segTime
      break
    }
  }

  const h = Math.floor(totalTime / 3600)
  const m = Math.floor((totalTime % 3600) / 60)
  const s = Math.floor(totalTime % 60)
  return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
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
  let totalTime = 0

  displaySegments.value.forEach(seg => {
    const segStart = seg.start_km || 0
    const segEnd = seg.end_km || seg.segment_km || 0

    if (segEnd > startKm && segStart < endKm) {
      const overlapStart = Math.max(segStart, startKm)
      const overlapEnd = Math.min(segEnd, endKm)
      const overlapDist = overlapEnd - overlapStart
      const segDist = segEnd - segStart
      const segTime = seg.avg_pace_min_per_km * segDist * 60
      const overlapTime = (overlapDist / segDist) * segTime
      totalTime += overlapTime
    }
  })

  const h = Math.floor(totalTime / 3600)
  const m = Math.floor((totalTime % 3600) / 60)
  const s = Math.floor(totalTime % 60)
  return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
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

  if (closest) {
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
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
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
  const tierMap = {
    'TIER_1_PHYSICS': 'Physics Baseline',
    'TIER_2_PARAMETER_LEARNING': 'Personalized Physics',
    'TIER_3_RESIDUAL_ML': 'ML Enhanced'
  }
  return tierMap[tier] || tier
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
