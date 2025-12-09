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
          <div class="text-2xl font-bold">{{ prediction.statistics.flat_pace_min_per_km.toFixed(2) }}</div>
          <div class="text-blue-100 text-sm">min/km (flat)</div>
        </div>
      </div>
    </div>

    <!-- Segment Breakdown -->
    <div class="bg-white p-6 rounded-lg shadow">
      <h3 class="text-xl font-bold mb-4">Segment Breakdown</h3>

      <div class="overflow-x-auto">
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
              :key="segment.segment_km"
              class="border-b hover:bg-gray-50"
            >
              <td class="px-4 py-2">Km {{ segment.segment_km }}</td>
              <td class="px-4 py-2 text-right">
                <span :class="getGradeColor(segment.avg_grade_percent)">
                  {{ segment.avg_grade_percent.toFixed(1) }}%
                </span>
              </td>
              <td class="px-4 py-2 text-right font-medium">{{ segment.time_formatted }}</td>
              <td class="px-4 py-2 text-right text-gray-600">
                {{ (segment.time_seconds / 60).toFixed(2) }} min/km
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
        <strong>Your flat pace:</strong> {{ prediction.statistics.flat_pace_min_per_km.toFixed(2) }} min/km
      </p>
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
        class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
      >
        Export Results
      </button>
    </div>
  </div>
</template>

<script setup>
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

const getGradeColor = (grade) => {
  if (grade > 5) return 'text-red-600 font-semibold'
  if (grade > 2) return 'text-orange-600'
  if (grade < -5) return 'text-green-600 font-semibold'
  if (grade < -2) return 'text-green-500'
  return 'text-gray-700'
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
  `Km ${s.segment_km}: ${s.time_formatted} (${s.avg_grade_percent.toFixed(1)}% grade)`
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
