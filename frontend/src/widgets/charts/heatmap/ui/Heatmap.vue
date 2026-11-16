<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { storeToRefs } from 'pinia'
import { Color } from '../../model/chart.types'
import { theme } from '../../model/heatmap-theme'
import { renderHeatmap } from '../render'
import { usePlotStore } from '../../../../entities/main/model/plot.store'
import { useMainEventStore } from '../../../../entities/main'
import { trialsOfRegion } from '../../../../entities/experiment/lib/regions'
import type { SearchSpaceRegion } from '../../../../entities/experiment/model/experiment.model'

defineOptions({ name: 'HeatmapChart' })

const plotStore = usePlotStore()
const store = useMainEventStore()
const { allRes, solution } = storeToRefs(plotStore)
const { specsByName, plotlyInstance } = storeToRefs(store)
const map = ref<HTMLElement | null>(null)

const props = defineProps<{
    region: SearchSpaceRegion
    heatmapParam1: string
    heatmapParam2: string
    heatmapObjective: string
}>()

// values that possible to use in template
const colors = Color

async function render() {
    await nextTick()

    if (!plotlyInstance.value) return
    if (!map.value) return
    // a trial of the region without a selected parameter is drawn as inactive in it; the solution is drawn only
    // in the region it belongs to
    const trials = trialsOfRegion(allRes.value, props.region)
    const [regionSolution = null] = trialsOfRegion(solution.value ? [solution.value] : [], props.region)
    renderHeatmap(
        plotlyInstance.value, map.value, trials, props.heatmapParam1, props.heatmapParam2, props.heatmapObjective,
        specsByName.value, regionSolution
    )
}

watch(
    [
        allRes,
        solution,
        () => props.heatmapParam1,
        () => props.heatmapParam2,
        () => props.heatmapObjective
    ],
    () => {
        render()
    },
    { deep: true }
)

// render once Plotly has finished loading; kept out of the deep watch above,
// which would otherwise traverse the whole Plotly object
watch(plotlyInstance, () => {
    render()
})

onMounted(() => {
    render()
})

onBeforeUnmount(() => {
    if (map.value && plotlyInstance.value) {
        plotlyInstance.value.purge(map.value)
    }
})
</script>

<template>
  <div>
    <div ref="map" />
    <select
      v-model="theme.color"
      @change="render"
    >
      <option
        v-for="col in colors"
        :key="col"
        :value="col"
      >
        {{ col }}
      </option>
    </select>
  </div>
</template>
