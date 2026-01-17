<template>
  <div class="stack">
    <div class="card stack">
      <div>
        <h2 class="section-title">Upload GPX File</h2>
        <p class="section-subtitle">Drop your route and start the prediction engine.</p>
      </div>

      <div v-if="!authStore.isAuthenticated" class="alert alert-warn">
        <p>Connect your Strava account to enable predictions.</p>
      </div>

      <div>
        <input
          type="file"
          accept=".gpx"
          @change="handleFileSelect"
          ref="fileInput"
          :disabled="!authStore.isAuthenticated"
          class="input-file"
        />
      </div>

      <div class="flex flex-wrap items-center gap-3">
        <button
          @click="uploadFile"
          :disabled="!authStore.isAuthenticated || !selectedFile || uploading"
          class="btn btn-primary disabled:opacity-50"
        >
          {{ uploading ? 'Uploading...' : 'Upload' }}
        </button>
        <p v-if="gpxStore.error" class="text-sm text-rose-600">{{ gpxStore.error }}</p>
      </div>
    </div>

    <div v-if="gpxStore.gpxList.length > 0" class="card stack">
      <div>
        <h2 class="section-title">Your GPX Files</h2>
        <p class="section-subtitle">Pick a file to predict, compare, and iterate.</p>
      </div>

      <div class="space-y-3">
        <div
          v-for="file in gpxStore.gpxList"
          :key="file.id"
          class="list-row"
        >
          <div>
            <p class="font-semibold text-slate-900">{{ file.original_filename }}</p>
            <p class="text-sm text-slate-600">
              Uploaded: {{ new Date(file.upload_date).toLocaleString() }}
            </p>
          </div>
          <div class="flex flex-wrap gap-2">
            <router-link
              :to="`/prediction/${file.id}`"
              class="btn btn-dark"
            >
              Predict
            </router-link>
            <button
              @click="deleteFile(file.id)"
              class="btn btn-danger"
            >
              Delete
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="!gpxStore.loading" class="card card-soft text-center">
      <p class="text-slate-600">No GPX files uploaded yet. Upload your first file to get started!</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useGpxStore } from '../stores/gpx'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const gpxStore = useGpxStore()
const authStore = useAuthStore()

const fileInput = ref(null)
const selectedFile = ref(null)
const uploading = ref(false)

onMounted(async () => {
  await authStore.checkAuthStatus()
  await gpxStore.fetchGpxList()
})

const handleFileSelect = (event) => {
  selectedFile.value = event.target.files[0]
}

const uploadFile = async () => {
  if (!authStore.isAuthenticated) return
  if (!selectedFile.value) return

  uploading.value = true
  try {
    const result = await gpxStore.uploadGpx(selectedFile.value)
    router.push(`/prediction/${result.id}`)
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
