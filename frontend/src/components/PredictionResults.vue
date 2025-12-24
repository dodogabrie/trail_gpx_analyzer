<template>
  <div class="space-y-6">
    <!-- Main Prediction Card -->
    <div class="bg-gradient-to-r from-blue-500 to-blue-600 text-white p-6 rounded-lg shadow-lg">
      <h3 class="text-2xl font-bold mb-4">Predicted Time</h3>

      <div class="text-center">
        <div class="text-5xl font-bold mb-2">
          {{ prediction.total_time_formatted }}
        </div>

        <div class="text-blue-100 text-sm">
          Confidence interval: {{ prediction.confidence_interval.lower_formatted }} -
          {{ prediction.confidence_interval.upper_formatted }}
        </div>
      </div>

      <div class="grid grid-cols-3 gap-4 mt-6 pt-6 border-t border-blue-400">
        <div class="text-center">
          <div class="text-2xl font-bold">{{ prediction.statistics.total_distance_km.toFixed(2) }}</div>
          <div class="text-blue-100 text-sm">km</div>
        </div>
        <div class="text-center">
          <div class="text-2xl font-bold">{{ Math.round(prediction.statistics.total_elevation_gain_m) }}</div>
          <div class="text-blue-100 text-sm">m gain</div>
        </div>
        <div class="text-center">
          <div class="text-2xl font-bold">{{ formatPace(prediction.statistics.flat_pace_min_per_km) }}</div>
          <div class="text-blue-100 text-sm">flat pace</div>
        </div>
      </div>
    </div>

    <!-- Actions -->
    <div class="flex gap-2">
      <button
        @click="$emit('recalibrate')"
        class="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
      >
        Recalibrate
      </button>
      <button
        @click="exportResults"
        class="px-4 py-2 bg-gray-100 text-gray-700 rounded hover:bg-gray-200 border"
      >
        Export Text
      </button>
      <button
        v-if="prediction.prediction_id"
        @click="exportVirtualPartner"
        class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 flex items-center gap-2 shadow-sm"
      >
        <span>🏃</span> Export Virtual Partner (GPX)
      </button>
    </div>

    <!-- Map Visualization -->
    <div class="bg-white p-1 rounded-lg shadow h-[500px] border relative">
      <div class="absolute top-4 right-4 z-[1000] bg-white/90 p-2 rounded shadow text-xs space-y-1 backdrop-blur-sm">
        <div class="font-bold mb-1">Pace Legend</div>
        <div class="flex items-center gap-2"><div class="w-3 h-3 bg-green-500 rounded"></div> Fast (Downhill)</div>
        <div class="flex items-center gap-2"><div class="w-3 h-3 bg-blue-500 rounded"></div> Flat / Steady</div>
        <div class="flex items-center gap-2"><div class="w-3 h-3 bg-yellow-500 rounded"></div> Moderate Climb</div>
        <div class="flex items-center gap-2"><div class="w-3 h-3 bg-red-500 rounded"></div> Steep Climb</div>
      </div>
      <MapView
        v-if="gpxStore.points.length"
        :points="gpxStore.points"
        :prediction-segments="prediction.segments"
        :flat-pace="prediction.statistics.flat_pace_min_per_km"
      />
      <div v-else class="flex items-center justify-center h-full text-gray-500">
        Loading map data...
      </div>
    </div>

    <!-- Elevation & Pace Profile -->
    <div class="bg-white p-6 rounded-lg shadow">
      <h3 class="text-xl font-bold mb-4">Elevation & Pace Profile</h3>
      <ElevationPaceProfile
        v-if="gpxStore.points.length"
        :points="gpxStore.points"
        :segments="prediction.segments"
        :average-pace="prediction.statistics.flat_pace_min_per_km"
      />
      <div v-else class="flex items-center justify-center h-[500px] text-gray-500">
        Loading profile data...
      </div>
    </div>

    <!-- Segment Breakdown -->
    <div class="bg-white p-6 rounded-lg shadow">
      <div
        @click="showSegments = !showSegments"
        class="flex items-center justify-between cursor-pointer hover:bg-gray-50 -m-6 p-6 rounded-lg transition-colors"
      >
        <h3 class="text-xl font-bold">Segment Breakdown</h3>
        <svg
          :class="['w-6 h-6 transition-transform', showSegments ? 'rotate-180' : '']"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
        </svg>
      </div>

      <div v-show="showSegments" class="overflow-x-auto mt-4">
        <table class="w-full text-sm">
          <thead class="bg-gray-50 border-b">
            <tr>
              <th class="px-4 py-2 text-left">Km</th>
              <th class="px-4 py-2 text-right">Avg Grade</th>
              <th class="px-4 py-2 text-right">Time</th>
              <th class="px-4 py-2 text-right">Pace</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="segment in prediction.segments"
              :key="segment.split_number || segment.segment_km"
              class="border-b hover:bg-gray-50"
            >
              <td class="px-4 py-2">
                <span v-if="segment.segment_km">Km {{ segment.segment_km }}</span>
                <span v-else>{{ segment.start_km }} - {{ segment.end_km }} km</span>
              </td>
              <td class="px-4 py-2 text-right">
                <span :class="getGradeColor(segment.avg_grade_percent)">
                  {{ segment.avg_grade_percent.toFixed(1) }}%
                </span>
              </td>
              <td class="px-4 py-2 text-right font-medium">{{ segment.time_formatted }}</td>
              <td class="px-4 py-2 text-right text-gray-600">
                {{ formatPace(segment.avg_pace_min_per_km) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Similar Activities -->
    <div v-if="similarActivities.length > 0" class="bg-white p-6 rounded-lg shadow">
      <h3 class="text-xl font-bold mb-4">Similar Past Activities</h3>

      <div class="space-y-2">
        <div
          v-for="activity in similarActivities"
          :key="activity.id"
          class="p-3 bg-gray-50 rounded border flex justify-between items-center"
        >
          <div>
            <p class="font-medium">{{ activity.name }}</p>
            <p class="text-sm text-gray-600">
              {{ (activity.distance / 1000).toFixed(2) }} km
              <span class="mx-2">•</span>
              {{ formatDate(activity.start_date) }}
            </p>
          </div>
          <div class="text-right">
            <div class="font-bold text-blue-600">
              {{ formatTime(activity.moving_time) }}
            </div>
            <div class="text-xs text-gray-500">actual time</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Calibration Info -->
    <div class="bg-gray-50 p-4 rounded text-sm text-gray-600">
      <p>
        <strong>Calibration source:</strong> {{ selectedActivity?.name || 'Unknown' }}
        ({{ selectedActivity?.distance_km }} km)
      </p>
      <p class="mt-1">
        <strong>Your flat pace:</strong> {{ formatPace(prediction.statistics.flat_pace_min_per_km) }}
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useGpxStore } from '../stores/gpx'
import MapView from './MapView.vue'
import ElevationPaceProfile from './ElevationPaceProfile.vue'
import api from '../services/api'

const gpxStore = useGpxStore()

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

const showSegments = ref(false)

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

const exportResults = () => {
  const text = `
Predicted Time: ${props.prediction.total_time_formatted}
Confidence: ${props.prediction.confidence_interval.lower_formatted} - ${props.prediction.confidence_interval.upper_formatted}

Statistics:
- Distance: ${props.prediction.statistics.total_distance_km.toFixed(2)} km
- Elevation Gain: ${Math.round(props.prediction.statistics.total_elevation_gain_m)} m
- Flat Pace: ${props.prediction.statistics.flat_pace_min_per_km.toFixed(2)} min/km

Segment Breakdown:
${props.prediction.segments.map(s =>
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