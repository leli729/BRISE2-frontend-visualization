<script setup lang="ts">
import { ref } from 'vue'
import { usePlotStore } from '../../../../entities/main/model/plot.store'
import { renderEdf } from '../render'
import { storeToRefs } from 'pinia'
import { useMainEventStore } from '../../../../entities/main'
import { useChartRender, CLIENT_REDRAW_INTERVAL_MS } from '../../model/use-chart-render'

defineOptions({ name: 'EdfChart' })

const props = withDefaults(defineProps<{
    active?: boolean
}>(), { active: true })

const plotStore = usePlotStore()
const store = useMainEventStore()
const { allRes } = storeToRefs(plotStore)
const { experiment_description, plotlyInstance } = storeToRefs(store)
const edf = ref<HTMLElement | null>(null)

function render() {
    if (!experiment_description.value) 
        return
    renderEdf(plotlyInstance.value!, edf.value!, allRes.value)
}

useChartRender({
    element: edf,
    plotly: plotlyInstance,
    sources: [
        allRes
    ],
    render,
    active: () => props.active,
    minIntervalMs: CLIENT_REDRAW_INTERVAL_MS
})
</script>



<template>
  <div
    ref="edf"
  />
</template>