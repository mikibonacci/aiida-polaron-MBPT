# Reference

Entry point: `polaron_mbpt` in the `aiida.workflows` group, class `aiida_polaron_mbpt.workflows.polaron_mbpt.PolaronMBPTWorkChain`.

## Inputs

| Input | Type | Required | Description |
|---|---|---|---|
| `structure` | `StructureData` | yes | Initial structure. |
| `pw_code` | `AbstractCode` | yes | Quantum ESPRESSO `pw.x`. |
| `pseudo_family` | `Str` | yes | Pseudo family label, used for all QE calculations. |
| `yambo_code` | `AbstractCode` | yes | Yambo main code. |
| `yambo_preprocessing_code` | `AbstractCode` | yes | `p2y`. |
| `hubbard_u_initial` | `Dict` | yes | U values for `relax_1`. |
| `hubbard_u_final` | `Dict` | yes | U values for `relax_2` and `relax_3`. |
| `hubbard_projectors` | `Str` | no | Default `atomic`. |
| `hubbard_formulation` | `Str` | no | Default `dudarev`. |
| `kpoints_gamma` | `KpointsData` | yes | Mesh for `relax_1` and `relax_2`. |
| `kpoints_relax3` | `KpointsData` | yes | Mesh for `relax_3`. |
| `kpoints_yambo` | `KpointsData` | no | Mesh for Yambo SCF/NSCF. Default: `kpoints_relax3`. |
| `max_force_threshold` | `Float` | no | Warning threshold, eV/Å. Default 0.2. |
| `max_structure_displacement` | `Float` | no | Warning threshold, Å. Default 0.5. |
| `relax_1`, `relax_2`, `relax_3` | namespaces | yes | `PwBaseWorkChain` inputs, without structure, code, pseudos, k-points and parent folder. |
| `yambo` | namespace | yes | `YamboWorkflow` inputs, without structure, codes, pseudos, k-points and parent folder. |

## Outputs

| Output | Type | Description |
|---|---|---|
| `relax_1`, `relax_2`, `relax_3` | namespaces | Outputs of each `PwBaseWorkChain`. |
| `yambo` | namespace | Outputs of the `YamboWorkflow`. |
| `relax_1_structure`, `relax_2_structure`, `relax_3_structure` | `StructureData` | Relaxed structure of each stage. |
| `final_structure` | `StructureData` | Alias of the stage-3 structure. |

## Exit codes

| Code | Name | Meaning |
|---|---|---|
| 401 | `ERROR_RELAX_1_FAILED` | The first relaxation failed. |
| 402 | `ERROR_RELAX_2_FAILED` | The second relaxation failed. |
| 403 | `ERROR_RELAX_3_FAILED` | The third relaxation failed. |
| 404 | `ERROR_YAMBO_FAILED` | The `YamboWorkflow` failed. |
| 405 | `ERROR_MISSING_OUTPUT_STRUCTURE` | A relaxation returned no structure. |
| 406 | `ERROR_MISSING_REMOTE_FOLDER` | `relax_1` returned no remote folder for the restart. |
| 407 | `ERROR_RELAX_3_FORCE_TOO_LARGE` | Final force above threshold. Warning-only for now. |
| 408 | `ERROR_RELAX_3_STRUCTURE_CHANGED` | Displacement above threshold. Warning-only for now. |
