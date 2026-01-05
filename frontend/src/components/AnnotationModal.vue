<template>
  <div v-if="show" class="fixed inset-0 z-50 flex items-center justify-end pointer-events-none">
    <div class="bg-white rounded-l-lg p-6 w-96 shadow-2xl pointer-events-auto max-h-[90vh] overflow-y-auto m-4">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-xl font-bold">Add Annotation</h3>
        <button @click="$emit('close')" class="text-gray-400 hover:text-gray-600 text-2xl leading-none">&times;</button>
      </div>

      <div class="mb-4">
        <label class="block text-sm font-medium mb-2 text-gray-700">Location</label>
        <p class="text-gray-900 font-semibold">{{ distanceKm.toFixed(2) }} km</p>
      </div>

      <div v-if="predictedTime" class="mb-4 p-3 bg-blue-50 border border-blue-200 rounded">
        <label class="block text-xs font-medium mb-1 text-blue-700">Predicted Time to Reach</label>
        <p class="text-blue-900 font-bold text-lg">{{ predictedTime }}</p>
      </div>

      <div class="mb-4">
        <label class="block text-sm font-medium mb-2 text-gray-700">Type</label>
        <div class="flex gap-4">
          <label class="flex items-center cursor-pointer">
            <input type="radio" v-model="annotationType" value="aid_station" class="mr-2">
            <span>Aid Station</span>
          </label>
          <label class="flex items-center cursor-pointer">
            <input type="radio" v-model="annotationType" value="generic" class="mr-2">
            <span>Generic</span>
          </label>
        </div>
      </div>

      <div class="mb-4">
        <label class="block text-sm font-medium mb-2 text-gray-700">Label</label>
        <input
          v-model="label"
          type="text"
          class="w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Edit label text..."
        >
        <p class="text-xs text-gray-500 mt-1">Format: Text - HH:MM:SS (time is predicted arrival)</p>
      </div>

      <div class="flex gap-2 justify-end mt-6">
        <button @click="$emit('close')" class="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 transition">
          Cancel
        </button>
        <button @click="save" class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition">
          Add Annotation
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  show: Boolean,
  distanceKm: Number,
  predictedTime: String
})

const emit = defineEmits(['close', 'save'])

const annotationType = ref('aid_station')
const label = ref('')

watch(() => props.show, (show) => {
  if (show) {
    annotationType.value = 'aid_station'
    label.value = props.predictedTime ? `Aid Station - ${props.predictedTime}` : 'Aid Station'
  }
})

watch(annotationType, (newType) => {
  if (newType === 'aid_station') {
    label.value = props.predictedTime ? `Aid Station - ${props.predictedTime}` : 'Aid Station'
  } else if (newType === 'generic') {
    label.value = props.predictedTime ? `Generic - ${props.predictedTime}` : 'Generic'
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
    label: label.value.trim()
  }

  emit('save', annotation)
  emit('close')
}
</script>
