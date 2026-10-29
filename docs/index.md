# aiida-polaron-MBPT

`aiida-polaron-MBPT` is an [AiiDA](https://www.aiida.net/) plugin with a single workflow, `PolaronMBPTWorkChain`. It takes a structure through three DFT+U ionic relaxations and then runs a [YAMBO](https://www.yambo-code.eu/) GW/BSE calculation on the relaxed geometry.

## What it does

1. DFT+U relaxation at Gamma, with the initial Hubbard U values.
2. A second relaxation with the final Hubbard U values. It restarts from the wavefunctions of stage 1.
3. A third relaxation with the final U values and a refined k-point mesh.
4. A DFT-only `YamboWorkflow` (SCF, NSCF, GW, QP, BSE), with the BSE run on top of the GW/QP results.

<div class="grid cards" markdown>

-   :material-download: **Install**

    [:octicons-arrow-right-24: Installation](installation.md)

-   :material-rocket-launch: **Launch the workflow**

    [:octicons-arrow-right-24: Usage](usage.md)

-   :material-sitemap: **How it works**

    [:octicons-arrow-right-24: Concepts](concepts.md)

-   :material-book-open-variant: **Inputs, outputs, exit codes**

    [:octicons-arrow-right-24: Reference](reference.md)

</div>

!!! warning "Norm-conserving pseudopotentials"
    The Yambo interface requires norm-conserving pseudopotentials. The examples use `PseudoDojo/0.4/PBE/SR/standard/upf`.
