<template>
  <div class="map-container" ref="mapContainer">
    <div class="layer-switcher">
      <button
        :class="{ active: currentLayer === 'topo' }"
        @click="switchToTopo"
        title="OpenTopoMap - Shows contour lines">
        Topo
      </button>
      <button
        :class="{ active: currentLayer === 'osm' }"
        @click="switchToOSM"
        title="OpenStreetMap - Detailed view">
        Street
      </button>
    </div>
  </div>
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
  },
  predictionSegments: {
    type: Array,
    default: null
  },
  flatPace: {
    type: Number,
    default: null
  },
  annotations: {
    type: Array,
    default: () => []
  }
})

const mapContainer = ref(null)
const mapStore = useMapStore()
const currentLayer = ref('topo')

let map = null
let routeLayer = L.layerGroup() // Changed to LayerGroup to hold multiple segments
let hoverMarker = null
let selectionLayer = null
let annotationMarkers = null
let topoLayer = null
let osmLayer = null

const initMap = () => {
  map = L.map(mapContainer.value).setView([mapStore.center.lat, mapStore.center.lon], mapStore.zoom)

  // OpenTopoMap layer (with contour lines, native tiles up to zoom 15)
  topoLayer = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
    attribution: 'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',
    maxNativeZoom: 15,
    maxZoom: 19
  })

  // Standard OSM layer (no contours, zoom 0-19)
  osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19
  })

  // Start with topo layer
  topoLayer.addTo(map)

  routeLayer.addTo(map)

  annotationMarkers = L.layerGroup()
  annotationMarkers.addTo(map)

  map.on('zoomend', () => {
    mapStore.updateZoom(map.getZoom())
  })

  map.on('moveend', () => {
    const center = map.getCenter()
    mapStore.updateCenter({ lat: center.lat, lon: center.lng })
  })
}

const getPaceColor = (pace, flatPace) => {
  if (!flatPace) return 'blue'
  const ratio = pace / flatPace
  
  if (ratio < 0.9) return '#22c55e' // Green (Fast/Downhill)
  if (ratio < 1.1) return '#3b82f6' // Blue (Flat/Normal)
  if (ratio < 1.4) return '#eab308' // Yellow (Moderate Climb)
  return '#ef4444' // Red (Steep Climb)
}

const drawRoute = (points) => {
  if (!map) return

  routeLayer.clearLayers()

  if (props.predictionSegments && props.flatPace) {
    // Draw colored segments
    let currentIndex = 0
    
    props.predictionSegments.forEach(seg => {
      const endDist = seg.end_km * 1000
      
      // Find end index for this segment
      let endIndex = currentIndex
      while (endIndex < points.length && points[endIndex].distance <= endDist) {
        endIndex++
      }
      // Include one extra point to connect segments
      const segmentPoints = points.slice(currentIndex, Math.min(endIndex + 1, points.length))
      
      if (segmentPoints.length > 1) {
        const latLngs = segmentPoints.map(p => [p.lat, p.lon])
        const color = getPaceColor(seg.avg_pace_min_per_km, props.flatPace)
        
        L.polyline(latLngs, {
          color: color,
          weight: 4,
          opacity: 0.8
        }).bindPopup(`
          <b>Segment Info</b><br>
          Grade: ${seg.avg_grade_percent.toFixed(1)}%<br>
          Pace: ${seg.avg_pace_min_per_km.toFixed(2)} min/km<br>
          Time: ${seg.time_formatted}
        `).addTo(routeLayer)
      }
      
      currentIndex = endIndex
    })
  } else {
    // Default blue line
    const latLngs = points.map(p => [p.lat, p.lon])
    L.polyline(latLngs, {
      color: 'blue',
      weight: 3,
      opacity: 0.7
    }).addTo(routeLayer)
  }

  // Fit bounds
  const latLngs = points.map(p => [p.lat, p.lon])
  if (latLngs.length > 0) {
    map.fitBounds(L.polyline(latLngs).getBounds())
  }
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

const switchToTopo = () => {
  if (!map) return
  if (map.hasLayer(osmLayer)) {
    map.removeLayer(osmLayer)
  }
  if (!map.hasLayer(topoLayer)) {
    topoLayer.addTo(map)
    topoLayer.redraw()
  }
  currentLayer.value = 'topo'
}

const switchToOSM = () => {
  if (!map) return
  if (map.hasLayer(topoLayer)) {
    map.removeLayer(topoLayer)
  }
  if (!map.hasLayer(osmLayer)) {
    osmLayer.addTo(map)
  }
  currentLayer.value = 'osm'
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

const updateAnnotationMarkers = (annotations) => {
  if (!annotationMarkers) return

  annotationMarkers.clearLayers()

  annotations.forEach(ann => {
    const targetDist = ann.distance_km * 1000
    let closest = null
    let minDiff = Infinity

    for (const point of props.points) {
      const diff = Math.abs(point.distance - targetDist)
      if (diff < minDiff) {
        minDiff = diff
        closest = point
      }
    }

    if (closest) {
      const icon = ann.type === 'aid_station'
        ? L.divIcon({
            html: '<div style="background: #10b981; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; white-space: nowrap; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">' + ann.label + '</div>',
            className: '',
            iconAnchor: [0, 40]
          })
        : L.divIcon({
            html: '<div style="background: #9333ea; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; white-space: nowrap; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">' + ann.label + '</div>',
            className: '',
            iconAnchor: [0, 40]
          })

      L.marker([closest.lat, closest.lon], { icon }).addTo(annotationMarkers)
    }
  })
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

watch(() => props.annotations, (annotations) => {
  updateAnnotationMarkers(annotations)
}, { deep: true, immediate: true })
</script>

<style scoped>
.map-container {
  width: 100%;
  height: 100%;
  border-radius: 8px;
  overflow: hidden;
  position: relative;
}

.layer-switcher {
  position: absolute;
  bottom: 10px;
  left: 10px;
  z-index: 1000;
  background: white;
  border-radius: 4px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.2);
  display: flex;
  overflow: hidden;
}

.layer-switcher button {
  padding: 6px 12px;
  border: none;
  background: white;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  color: #333;
  transition: all 0.2s;
}

.layer-switcher button:hover {
  background: #f0f0f0;
}

.layer-switcher button.active {
  background: #3b82f6;
  color: white;
}

.layer-switcher button:not(:last-child) {
  border-right: 1px solid #e0e0e0;
}
</style>
