import { defineStore } from 'pinia'

export const useMapStore = defineStore('map', {
  state: () => ({
    zoom: 11,
    center: { lat: 45.0, lon: 7.0 },
    hoveredPoint: null,
    selectedRange: null
  }),

  actions: {
    updateZoom(zoom) {
      this.zoom = zoom
    },

    updateCenter(center) {
      this.center = center
    },

    setHoveredPoint(index) {
      this.hoveredPoint = index
    },

    setSelectedRange(range) {
      this.selectedRange = range
    },

    clearHover() {
      this.hoveredPoint = null
    },

    clearSelection() {
      this.selectedRange = null
    }
  }
})
