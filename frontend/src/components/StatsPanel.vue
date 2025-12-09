<template>
  <div v-if="stats" class="bg-white p-4 rounded-lg shadow h-full">
    <h3 class="text-base font-bold mb-3">Selected Segment</h3>
    <div class="space-y-4">
      <div>
        <p class="text-xs text-gray-600">Distance</p>
        <p class="text-2xl font-bold">{{ (stats.distance / 1000).toFixed(2) }} km</p>
      </div>
      <div>
        <p class="text-xs text-gray-600">Elevation Gain (D+)</p>
        <p class="text-2xl font-bold text-green-600">{{ stats.elevation_gain.toFixed(0) }} m</p>
      </div>
      <div>
        <p class="text-xs text-gray-600">Elevation Loss (D-)</p>
        <p class="text-2xl font-bold text-red-600">{{ stats.elevation_loss.toFixed(0) }} m</p>
      </div>
    </div>
  </div>
  <div v-else class="bg-white p-4 rounded-lg shadow h-full flex items-center justify-center">
    <p class="text-gray-500 text-sm text-center">Select a segment on the elevation profile</p>
  </div>
</template>

<script setup>
defineProps({
  stats: {
    type: Object,
    default: null
  }
})
</script>
