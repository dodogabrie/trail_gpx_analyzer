<template>
  <div class="space-y-6">
    <div class="bg-white p-6 rounded-lg shadow">
      <h2 class="text-2xl font-bold mb-4">Upload GPX File</h2>

      <div class="mb-4">
        <input
          type="file"
          accept=".gpx"
          @change="handleFileSelect"
          ref="fileInput"
          class="block w-full text-sm text-gray-500
            file:mr-4 file:py-2 file:px-4
            file:rounded file:border-0
            file:text-sm file:font-semibold
            file:bg-blue-50 file:text-blue-700
            hover:file:bg-blue-100"
        />
      </div>

      <button
        @click="uploadFile"
        :disabled="!selectedFile || uploading"
        class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
      >
        {{ uploading ? 'Uploading...' : 'Upload' }}
      </button>

      <p v-if="gpxStore.error" class="text-red-600 mt-2">{{ gpxStore.error }}</p>
    </div>

    <div v-if="gpxStore.gpxList.length > 0" class="bg-white p-6 rounded-lg shadow">
      <h2 class="text-2xl font-bold mb-4">Your GPX Files</h2>

      <div class="space-y-2">
        <div
          v-for="file in gpxStore.gpxList"
          :key="file.id"
          class="flex justify-between items-center p-3 bg-gray-50 rounded border"
        >
          <div>
            <p class="font-medium">{{ file.original_filename }}</p>
            <p class="text-sm text-gray-600">
              Uploaded: {{ new Date(file.upload_date).toLocaleString() }}
            </p>
          </div>
          <div class="space-x-2">
            <router-link
              :to="`/analysis/${file.id}`"
              class="px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 text-sm"
            >
              Analyze
            </router-link>
            <button
              @click="deleteFile(file.id)"
              class="px-3 py-1 bg-red-500 text-white rounded hover:bg-red-600 text-sm"
            >
              Delete
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="!gpxStore.loading" class="bg-white p-6 rounded-lg shadow text-center">
      <p class="text-gray-500">No GPX files uploaded yet. Upload your first file to get started!</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useGpxStore } from '../stores/gpx'

const router = useRouter()
const gpxStore = useGpxStore()

const fileInput = ref(null)
const selectedFile = ref(null)
const uploading = ref(false)

onMounted(async () => {
  await gpxStore.fetchGpxList()
})

const handleFileSelect = (event) => {
  selectedFile.value = event.target.files[0]
}

const uploadFile = async () => {
  if (!selectedFile.value) return

  uploading.value = true
  try {
    const result = await gpxStore.uploadGpx(selectedFile.value)
    router.push(`/analysis/${result.id}`)
  } catch (error) {
    console.error('Upload failed:', error)
  } finally {
    uploading.value = false
    selectedFile.value = null
    if (fileInput.value) {
      fileInput.value.value = ''
    }
  }
}

const deleteFile = async (id) => {
  if (confirm('Are you sure you want to delete this GPX file?')) {
    await gpxStore.deleteGpx(id)
  }
}
</script>
