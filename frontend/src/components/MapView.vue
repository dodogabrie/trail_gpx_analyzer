<template>
  <div class="map-container" ref="mapContainer"></div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useMapStore } from '../stores/map'

const props = defineProps({
  points: {
    type: Array,
    required: true
  },
  hoveredIndex: {
    type: Number,
    default: null
  },
  selectedRange: {
    type: Object,
    default: null
  }
})

const mapContainer = ref(null)
const mapStore = useMapStore()

let map = null
let routeLayer = null
let hoverMarker = null
let selectionLayer = null

const initMap = () => {
  map = L.map(mapContainer.value).setView([mapStore.center.lat, mapStore.center.lon], mapStore.zoom)

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map)

  map.on('zoomend', () => {
    mapStore.updateZoom(map.getZoom())
  })

  map.on('moveend', () => {
    const center = map.getCenter()
    mapStore.updateCenter({ lat: center.lat, lon: center.lng })
  })
}

const drawRoute = (points) => {
  if (!map) return

  if (routeLayer) {
    map.removeLayer(routeLayer)
  }

  const latLngs = points.map(p => [p.lat, p.lon])

  routeLayer = L.polyline(latLngs, {
    color: 'blue',
    weight: 3,
    opacity: 0.7
  }).addTo(map)

  map.fitBounds(routeLayer.getBounds())
}

const updateHoverMarker = (index) => {
  if (hoverMarker) {
    map.removeLayer(hoverMarker)
    hoverMarker = null
  }

  if (index !== null && props.points[index]) {
    const point = props.points[index]
    hoverMarker = L.circleMarker([point.lat, point.lon], {
      radius: 4,
      color: '#000',
      fillColor: '#000',
      fillOpacity: 1,
      weight: 2
    }).addTo(map)
  }
}

const updateSelection = (range) => {
  if (selectionLayer) {
    map.removeLayer(selectionLayer)
    selectionLayer = null
  }

  if (range && range.start !== null && range.end !== null) {
    const selectedPoints = props.points.slice(range.start, range.end + 1)
    const latLngs = selectedPoints.map(p => [p.lat, p.lon])

    selectionLayer = L.polyline(latLngs, {
      color: 'red',
      weight: 5,
      opacity: 0.9
    }).addTo(map)
  }
}

onMounted(() => {
  initMap()
  if (props.points && props.points.length > 0) {
    drawRoute(props.points)
  }
})

watch(() => props.points, (newPoints) => {
  if (newPoints && newPoints.length > 0) {
    drawRoute(newPoints)
  }
})

watch(() => props.hoveredIndex, (index) => {
  updateHoverMarker(index)
})

watch(() => props.selectedRange, (range) => {
  updateSelection(range)
})
</script>

<style scoped>
.map-container {
  width: 100%;
  height: 100%;
  border-radius: 8px;
  overflow: hidden;
}
</style>
