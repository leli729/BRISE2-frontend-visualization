import { defineStore } from 'pinia'
import { ref, shallowRef } from 'vue'

export interface PointExp {
    configurations: Record<string, any>;
    results: Record<string, any>;
    time: string;
    "measured points": number;
}

export const usePlotStore = defineStore('plots', () => {
    const selected = ref({
        "Optimization History": false,
        "Parallel Coordinates": false,
        "Rank Plot": false,
        "Hyperparameter Importances": false,
        "Slice Plot": false,
        "Contour Plot": false,
        "Pareto Front": false,
        "EDF Plot": false,
        "Heatmap": false,
        // "Heatmap Reg": false, // disabled, see the HeatmapReg import comment in App.vue
    })
    
    const visibleCharts = ref<string[]>([])

    // shallow: a change is the assignment of a new array (points are appended as `allRes.value = [...allRes.value, point]`),
    // so a watcher costs nothing per point instead of a traversal of all of them
    const allRes = shallowRef<PointExp[]>([])

    const canChangeVisibleCharts = ref(false)

    // final configuration suggested by BRISE
    const solution = ref<PointExp | null>(null)
    
    // forgets the previous experiment: its measured points and the charts it selected
    function clearCharts() {
        allRes.value = []
        solution.value = null
        for (const chart of Object.keys(selected.value) as Array<keyof typeof selected.value>) {
            selected.value[chart] = false
        }
        visibleCharts.value = []
    }

    return {
        selected,
        visibleCharts,
        allRes,
        canChangeVisibleCharts,
        solution,
        clearCharts
    }
})