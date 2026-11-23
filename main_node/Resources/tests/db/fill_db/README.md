# Inputs of the `fill_db` scenario

The product configurations the benchmark's [`fill_db`](../../../../../benchmark/benchmark_runner.py) scenario runs to fill the test database (see [`../README.md`](../README.md)), and the Waffle models they come from. The runs become the source experiments of the transfer-learning tests: a target finds a source only if it has the same search space, the same structure, the same objectives (names, directions, data types and expected ranges), the same sampler with the same seed and the same default configuration handler.

The scenario sets the sampler (Sobol and Mersenne Twister, seed 1), the default configuration handler (basic and random), the stop condition (30 configurations or 4 minutes, whichever comes first, so that every source holds predictions to transfer after its landmarks), the asynchronous distribution (a batched one waits for a wave of `BatchSize` configurations, which the 3 workers cannot fill) and `MinNumberOfSamples` itself; they are not part of the inputs.

Names: `<search space>-<objective direction>-<structure>`. A space whose parameters are all on one level (2-float, float-nom) is the same space in both structures, so it has no hierarchical input.

| Input | Model (`models/`) | Origin | Read by the target |
|---|---|---|---|
| `2-float-min-flat` | `2-float-min` | walk of test case 0 with a Gaussian process as surrogate | test cases 0, 10, 14 |
| `2-float-max-flat` | `2-float-max` | walk of test case 0 with the objective maximized and a Gaussian process as surrogate | generated 2-float products |
| `float-nom-min-flat` | `float-nom-min` | walk of test case 4 with a Gaussian process as surrogate and the mock validator | test cases 4, 9, 17 |
| `all-types-min-flat` | `all-types-min` | test case 13 | test case 13 |
| `all-types-min-hierarchical` | `all-types-min` | walk of test case 13 with the hierarchical structure (`N0` on level 0, its children on level 1, a model per level) | generated all-types products |
| `all-types-max-hierarchical` | `all-types-max` | walk of test case 11 | test cases 11, 12 |
| `int-cat-min-flat` | `int-cat-min` | walk of the generator's int-cat product `config_12_int-cat-so` with one algorithm and larger integers (see below) | generated int-cat products |
| `int-cat-min-hierarchical` | `int-cat-min` | walk of `int-cat-min-flat` with the hierarchical structure, one algorithm and larger integers | generated int-cat products |

Only single-objective products: the feature model forbids transfer learning for more than one objective. A maximizing input exists only where a target maximizes. The generated contexts take the search spaces of these inputs (`CONTEXT_SEARCH_SPACE_BOUNDS` of the test generator).

## Surrogate of the 2-float and float-nom inputs

A transfer-learning test case recommends the model of its source, and five tests assert that the recommended surrogate is a Gaussian process (test cases 0, 10, 14 and two tests of `transfer_learning/tests/test_mr.py`), so the 2-float and float-nom sources run one. The test cases' own surrogates (a tree-structured Parzen estimator, a Bayesian ridge regression) would hand over themselves, and float-nom's quality validator (threshold 0.5) would reject the models on the worker's random results, so the source would never predict. Both inputs differ from the test cases in the surrogate only (the 2-float optimizer also has no acquisition function, which the feature model allows with a tree-structured Parzen estimator only; float-nom has the mock validator); the optimizer, the candidate selector and the window are the test cases'. The sources of the other contexts keep the models of their test cases or of the generator.

## Int-cat

The generator's int-cat product runs six MOEA algorithms in every prediction (9.7 s per proposal against 0.2 s for GACO alone) in a space of 44 configurations, in which the proposals of a model are mostly evaluated already, so a source predicted in 2 of 16 proposals. The int-cat inputs run GACO only (2 generations, population 70: GACO needs a population of at least its kernel size) and their integers are in [0, 1000] (4004 configurations, 16 of 16 proposals new). More categories gain nothing and would change the context model.

## Models

`models/` holds copies of Waffle models, each differing from `../../waffle_models/base.wfl` only in its context (they are checked by `../../test_wfl_copies_in_sync.py`): `2-float-min`, `float-nom-min` and `all-types-min` are the models of the test cases; `2-float-max`, `int-cat-min` come from the test generator (`WaffleTestingModels/`); `all-types-max` is `all-types-min` with `[Minimization = false]`.

## Manual fixes

Products are walked in Waffle and then fixed by hand, as for the test cases:
* `int-cat-min-flat`, `int-cat-min-hierarchical`: set `QualityThreshold: -100` (the model requires a value of at least 0) and `Weights: [1]` (Waffle leaves it empty for one objective). The task settings are those of the test cases (`MaxTimeToRunTask: 10` seconds); the generator's product has 0.

The other inputs need no fixes.
