<template>
  <div v-if="loading" class="text-center py-12">
    <p class="text-xl text-slate-600">Loading GPX data...</p>
  </div>

  <div v-else-if="error" class="text-center py-12">
    <p class="text-xl text-rose-600">{{ error }}</p>
    <router-link to="/" class="link mt-4 inline-block">
      Back to Home
    </router-link>
  </div>

  <div v-else class="flex flex-col h-screen overflow-hidden">
    <!-- Main content: Map only -->
    <div class="flex flex-1 min-h-0 p-3">
      <div class="flex-1 min-w-0 relative">
        <!-- Floating GPX info bubble -->
        <div class="absolute top-3 right-3 rounded-xl border border-white/70 bg-white/85 px-3 py-2 shadow-lg backdrop-blur-sm z-[1000] pointer-events-none">
          <p class="text-sm font-semibold truncate max-w-xs">{{ gpxStore.currentGpx?.original_filename }}</p>
          <p class="text-xs text-slate-600">{{ (gpxStore.totalDistance / 1000).toFixed(2) }} km</p>
        </div>

        <MapView
          :points="gpxStore.points"
          :hoveredIndex="mapStore.hoveredPoint"
          :selectedRange="mapStore.selectedRange"
        />
      </div>
    </div>

    <!-- Elevation profile at bottom -->
    <div class="flex-shrink-0 px-3 pb-3 relative">
      <!-- Stats overlay on elevation chart -->
      <div v-if="stats" class="absolute top-2 right-6 rounded-xl border border-white/70 bg-white/85 px-3 py-2 shadow-lg backdrop-blur-sm z-10 text-xs">
        <div class="flex gap-4">
          <div>
            <span class="text-slate-600">Dist:</span>
            <span class="font-bold ml-1">{{ (stats.distance / 1000).toFixed(2) }} km</span>
          </div>
          <div>
            <span class="text-slate-600">D+:</span>
            <span class="font-bold text-emerald-600 ml-1">{{ stats.elevation_gain.toFixed(0) }} m</span>
          </div>
          <div>
            <span class="text-slate-600">D-:</span>
            <span class="font-bold text-rose-600 ml-1">{{ stats.elevation_loss.toFixed(0) }} m</span>
          </div>
        </div>
      </div>

      <ElevationProfile
        :points="gpxStore.points"
        @hover="handleHover"
        @select="handleSelect"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useGpxStore } from '../stores/gpx'
import { useMapStore } from '../stores/map'
import MapView from '../components/MapView.vue'
import ElevationProfile from '../components/ElevationProfile.vue'
import api from '../services/api'

const route = useRoute()
const gpxStore = useGpxStore()
const mapStore = useMapStore()

const gpxId = ref(route.params.gpxId)
const loading = ref(true)
const error = ref(null)
const stats = ref(null)

onMounted(async () => {
  try {
    await gpxStore.fetchGpxData(gpxId.value)
  } catch (err) {
    error.value = err.message || 'Failed to load GPX data'
  } finally {
    loading.value = false
  }
})

watch(() => mapStore.selectedRange, async (range) => {
  if (range && range.start !== null && range.end !== null) {
    try {
      const response = await api.post('/analysis/stats', {
        gpx_id: parseInt(gpxId.value),
        start_index: range.start,
        end_index: range.end
      })
      stats.value = response.data
    } catch (err) {
      console.error('Failed to calculate stats:', err)
    }
  } else {
    stats.value = null
  }
})

const handleHover = (index) => {
  mapStore.setHoveredPoint(index)
}

const handleSelect = (range) => {
  mapStore.setSelectedRange(range)
}
</script>
