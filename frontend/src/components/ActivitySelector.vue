<template>
  <div class="space-y-4">
    <div>
      <h3 class="text-xl font-bold mb-2">Select Calibration Activity</h3>
      <p class="text-gray-600 text-sm">
        Choose a recent activity to calibrate your pace. Activities similar to your route are marked as recommended.
      </p>
    </div>

    <div v-if="predictionStore.loading" class="text-center py-8">
      <p class="text-gray-500">Loading activities...</p>
    </div>

    <div v-else-if="predictionStore.error" class="bg-red-50 border border-red-200 rounded p-4">
      <p class="text-red-600">{{ predictionStore.error }}</p>
    </div>

    <div v-else class="space-y-2 max-h-96 overflow-y-auto">
      <div
        v-for="activity in predictionStore.calibrationActivities"
        :key="activity.strava_id"
        @click="selectActivity(activity)"
        :class="[
          'p-4 border rounded cursor-pointer transition-colors',
          activity.recommended
            ? 'border-blue-400 bg-blue-50 hover:bg-blue-100'
            : 'border-gray-200 bg-white hover:bg-gray-50'
        ]"
      >
        <div class="flex justify-between items-start">
          <div class="flex-1">
            <div class="flex items-center gap-2">
              <h4 class="font-medium">{{ activity.name }}</h4>
              <span
                v-if="activity.recommended"
                class="px-2 py-0.5 bg-blue-500 text-white text-xs rounded"
              >
                Recommended
              </span>
            </div>
            <div class="text-sm text-gray-600 mt-1">
              <span>{{ activity.distance_km }} km</span>
              <span class="mx-2">•</span>
              <span>{{ formatDate(activity.start_date) }}</span>
            </div>
          </div>
          <button
            @click.stop="selectActivity(activity)"
            class="px-3 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600"
          >
            Select
          </button>
        </div>
      </div>

      <div v-if="predictionStore.calibrationActivities.length === 0"
           class="text-center py-8 text-gray-500">
        No activities found. Make sure you have connected your Strava account.
      </div>
    </div>
  </div>
</template>

<script setup>
import { usePredictionStore } from '../stores/prediction'

const predictionStore = usePredictionStore()

const props = defineProps({
  gpxId: {
    type: Number,
    required: true
  }
})

const emit = defineEmits(['activity-selected'])

const selectActivity = async (activity) => {
  console.log('🎯 Activity selected:', activity.name, 'ID:', activity.strava_id)
  console.log('📍 GPX ID:', props.gpxId)

  try {
    await predictionStore.calibrateFromActivity(activity.strava_id, props.gpxId)
    console.log('✅ Calibration completed')
    emit('activity-selected', activity)
  } catch (error) {
    console.error('❌ Failed to calibrate:', error)
  }
}

const formatDate = (dateStr) => {
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  })
}
</script>
