# v0.9.0 transition first-sample throughput analysis

## Purpose

This report analyses the first recorded sample after each commanded-load transition in the published v0.8.0 dynamic-identification dataset.

The analysis focuses on the throughput channel:

    u_cmd(t) -> u_ach(t)

## Persistent identifiers

- Software v0.8.0 DOI: `10.5281/zenodo.20828274`
- Dataset v0.8.0 DOI: `10.5281/zenodo.20834551`

## Method

For every row where `u_cmd` changes relative to the previous row, the transition coefficient was computed as:

    alpha = (u_ach[k] - u_ach[k-1]) / (u_cmd[k] - u_ach[k-1])

This gives the fraction of the transition completed by the first recorded post-transition sample.

The corresponding one-step transition model is:

    y[k] = y[k-1] + alpha * (u[k] - y[k-1])

or equivalently:

    y[k] = (1 - alpha) * y[k-1] + alpha * u[k]

## Transition-row dataset

- transition rows: 26
- upward transitions: 13
- downward transitions: 13
- observed boundary `dt`: approximately 35.02 seconds

Important note: the analysed row is the first recorded post-transition sample in the CSV. It should not be interpreted as a 5-second transient sample. Although the nominal collection sample interval is 5 seconds, the observed interval across segment boundaries in these records is approximately 35 seconds.

## Results

### Transition coefficient alpha

| subset | n | mean alpha | min alpha | max alpha |
|---|---:|---:|---:|---:|
| all | 26 | 0.856154 | 0.848629 | 0.861736 |
| upward transitions | 13 | 0.855481 | 0.848629 | 0.857413 |
| downward transitions | 13 | 0.856827 | 0.854102 | 0.861736 |

### First recorded post-transition error

| subset | n | mean error | min error | max error |
|---|---:|---:|---:|---:|
| all | 26 | -0.004269 | -13.800986 | 13.745114 |
| upward transitions | 13 | -6.007425 | -13.800986 | -0.878283 |
| downward transitions | 13 | 5.998886 | 0.836479 | 13.745114 |

## Derived transition model

Using the aggregate mean value:

    alpha = 0.856154

the transition model becomes:

    y[k] = y[k-1] + 0.856154 * (u[k] - y[k-1])

or:

    y[k] = 0.143846 * y[k-1] + 0.856154 * u[k]

## Interpretation

The transition coefficient is highly consistent across upward and downward transitions.

By the first recorded post-transition sample, approximately 85.6% of the throughput transition has already occurred. The remaining error is direction-dependent:

- upward transitions remain below the new command;
- downward transitions remain above the new command.

This is consistent with a first-order lag-like response.

The settled-sample unity-baseline result remains valid for steady-state modelling, while this transition analysis provides a simple first-order correction for boundary samples.

## Limitations

This analysis is based only on the first recorded sample after each `u_cmd` transition.

The observed boundary interval is approximately 35 seconds, so this analysis does not identify sub-35-second transient dynamics. A future experiment with denser sampling around command changes is required for finer dynamic identification.
