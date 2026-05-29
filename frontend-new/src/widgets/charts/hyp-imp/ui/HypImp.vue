<script setup lang="ts">
import { ref, onMounted, watch, computed} from 'vue'
import { storeToRefs } from 'pinia'


// Plotly
import Plotly from 'plotly.js-dist-min'

import { MainEvent } from '../../../../entities/main'

//service
import { useMainEventStore } from '../../../../entities/main'
import { OptunaService } from '../../../../services/OptunaService';

export interface Trial {
    parameters: Record<string, any>;
    objectives: Record<string, any>;
}

export interface InputData {
    experiment_description: any;
    trials: Trial[];
}

const optunaService = new OptunaService()

const isVisible = ref(false)

const trials = ref<Trial[]>([])
const store = useMainEventStore()
const { experiment_description } = storeToRefs(store)
const hypimp = ref<HTMLElement | null>(null)

const input_data = computed(() => ({
    experiment_description: experiment_description.value,
    trials: trials.value
}))

const importances = ref<Record<string, number>>({})
const isPyodideReady = ref(false)

const initialized = ref(false)

async function initPyodide() {
    await optunaService.init()
    isPyodideReady.value = true

    console.log("✅ Pyodide ready")
}

onMounted(() => {
    watch(experiment_description, () => {
        if (initialized.value) {
            return
            }
        const selectedHyperparameterImportances = experiment_description.value?.PlotSelection?.Plot?.HyperparameterImportances
        if (!selectedHyperparameterImportances) {
            return
            }
        initialized.value = true
        initPyodide() 
        initMainEvents() 
    }),
    {
        immediate: true,
        deep: true
    }         
})

async function calculateImportances() {
    const result = await optunaService.runPythonWithParams(
      `
        import optuna 
        FloatDistribution = optuna.distributions.FloatDistribution
        IntDistribution = optuna.distributions.IntDistribution
        CategoricalDistribution = (
            optuna.distributions.CategoricalDistribution
        )
        
        create_trial = optuna.trial.create_trial
        import json

        input_data = json.loads(input_data)

        # ============================================================
        # BUILD OPTUNA DISTRIBUTIONS
        # ============================================================

        def build_distributions(search_space):

            distributions = {}

            for param_name, param_data in search_space.items():

                if param_name == "Structure":
                    continue

                hp_type = param_data.get("Type")

                # ----------------------------------------------------
                # FLOAT
                # ----------------------------------------------------

                if hp_type == "FloatHyperparameter":

                    distributions[param_name] = FloatDistribution(
                        low=param_data["Lower"],
                        high=param_data["Upper"]
                    )

                # ----------------------------------------------------
                # INTEGER
                # ----------------------------------------------------

                elif hp_type == "IntegerHyperparameter":

                    distributions[param_name] = IntDistribution(
                        low=param_data["Lower"],
                        high=param_data["Upper"]
                    )

                # ----------------------------------------------------
                # ORDINAL / NOMINAL
                # ----------------------------------------------------

                elif hp_type in [
                    "OrdinalHyperparameter",
                    "NominalHyperparameter"
                ]:

                    distributions[param_name] = (
                        CategoricalDistribution(
                            choices=param_data["Categories"]
                        )
                    )

            return distributions


        # ============================================================
        # BUILD OPTIMIZATION DIRECTIONS
        # ============================================================

        def build_directions(objectives):

            directions = []

            for _, objective in objectives.items():

                if objective["Minimization"] is True:
                    directions.append("minimize")
                else:
                    directions.append("maximize")

            return directions


        # ============================================================
        # EXTRACT OBJECTIVE VALUES
        # ============================================================

        def extract_objective_values(objectives_dict):

            return list(objectives_dict.values())


        # ============================================================
        # RECONSTRUCT OPTUNA STUDY
        # ============================================================

        def reconstruct_study(input_data):

            experiment_description = (
                input_data["experiment_description"]
            )

            search_space = (
                experiment_description["Context"]
                ["SearchSpace"]
            )

            objectives = (
                experiment_description["Context"]
                ["TaskConfiguration"]
                ["Objectives"]
            )

            directions = build_directions(objectives)

            distributions = build_distributions(
                search_space
            )

            # --------------------------------------------------------
            # CREATE STUDY
            # --------------------------------------------------------

            if len(directions) == 1:

                study = optuna.create_study(
                    direction=directions[0]
                )

            else:

                study = optuna.create_study(
                    directions=directions
                )

            # --------------------------------------------------------
            # ADD TRIALS
            # --------------------------------------------------------

            for t in input_data["trials"]:

                params = t["parameters"]

                objective_values = extract_objective_values(
                    t["objectives"]
                )

                # SINGLE OBJECTIVE
                if len(objective_values) == 1:

                    frozen_trial = create_trial(
                        params=params,
                        distributions=distributions,
                        value=objective_values[0]
                    )

                # MULTI OBJECTIVE
                else:

                    frozen_trial = create_trial(
                        params=params,
                        distributions=distributions,
                        values=objective_values
                    )

                study.add_trial(frozen_trial)

            return study


        # ============================================================
        # PARAMETER IMPORTANCE
        # ============================================================

        def calculate_importances(input_data):

            study = reconstruct_study(input_data)

            importances = (
                optuna.importance.get_param_importances(
                    study
                )
            )

            return importances

        # ============================================================
        # MAIN ENTRYPOINT
        # ============================================================
        def run(input_data):
            if not input_data["trials"]:
                return {}
            return {
                "importances":
                    calculate_importances(input_data)
            }
        run(input_data)
      ` , 
      input_data.value   
    )
    importances.value = Object.fromEntries(result.get("importances"))
}

function initMainEvents() {
    watch(experiment_description, () => {
        trials.value = []
        importances.value = {}
        // pointer to dom element 
        const element = hypimp.value
        isVisible.value = false
        if (element)
            Plotly.purge(element)
    }, {
        deep: true,
        immediate: true
    })

    // add start point
    store.onEvent(MainEvent.DEFAULT)?.subscribe((message: any) => {
        if (message.headers['message_subtype'] === 'configuration') {
            const configs = JSON.parse(message.body)
            configs.forEach((configuration: any) => {
                const first_trial: Trial = {
                    parameters: configuration.configurations,
                    objectives: configuration.results
                };
               trials.value.push(first_trial);
            })
        }
    })

    // add last point
    store.onEvent(MainEvent.FINAL)?.subscribe((message: any) => {
        if (message.headers['message_subtype'] === 'configuration') {
            const configs = JSON.parse(message.body);
            configs.forEach((configuration: any) => {
                const last_trial: Trial = {
                    parameters: configuration.configurations,
                    objectives: configuration.results
                };
               trials.value.push(last_trial); 
            });
        }
        if (isPyodideReady) {
            render() // Render chart if pyodide ready
        }
    })

    // add new point
    store.onEvent(MainEvent.NEW)?.subscribe((message: any) => {
        if (message.headers['message_subtype'] === 'configuration') {
            const configs = JSON.parse(message.body);
            configs.forEach((configuration: any) => {
                const new_trial: Trial = {
                    parameters: configuration.configurations,
                    objectives: configuration.results
                };
               trials.value.push(new_trial);
            })
            if (isPyodideReady) {
                render()
            }
        }
    })
}

async function render() {
    // DOM element. Render point
    const element = hypimp.value
    if (!element) return

    if (trials.value.length <= 1) {
        console.warn("Needs more than 1 trial to calculate importances. Currently 1 or 0.")
        return
    }

    isVisible.value = true
    try {
        await calculateImportances()
    } catch(e) {
        console.error("❌ Pyodide crashed:", e)
    }

    const labels = Object.keys(importances.value)
    const values = Object.values(importances.value)

    const data = [
        {          
            x: labels,
            y: values,
            type: 'bar' as const
        }
    ]

    const layout = {
        title: {
            text: 'Hyperparameter Importances'
        },
        autosize: true,
        xaxis: {
            title: {
                text: 'Hyperparameters'
            }
        },

        yaxis: {
            title: {
                text: 'Importance'
            },
            range: [0, 1]
        }
    }
    if (element)
        Plotly.react(element, data, layout);
}
</script>

<template>
    <div v-show="isVisible" ref="hypimp"></div>
</template>