# Concepts

```
structure ──► relax_1 ──► relax_2 ──► relax_3 ──► YamboWorkflow
              U initial   U final     U final     SCF → NSCF → GW/QP → BSE
              Gamma       Gamma       refined k   (on relax_3 structure)
                 └─wavefunctions─┘
```

## Stages

| Stage | U values | k-points | Notes |
|---|---|---|---|
| `relax_1` | `hubbard_u_initial` | `kpoints_gamma` | Starting relaxation. |
| `relax_2` | `hubbard_u_final` | `kpoints_gamma` | Restarts from the stored wavefunctions of `relax_1`. |
| `relax_3` | `hubbard_u_final` | `kpoints_relax3` | Refined mesh. Its structure feeds Yambo. |
| `yambo` | none (DFT only) | `kpoints_yambo` | `YamboWorkflow`: SCF, NSCF, GW, QP, then BSE on top of GW/QP. |

The final structure is returned as `final_structure`.

## Why `PwBaseWorkChain`

Each relaxation is a `PwBaseWorkChain` with `CONTROL.calculation = "relax"`. This is intentional. The public `PwRelaxWorkChain` interface excludes external `parent_folder` inputs, while `PwBaseWorkChain` supports the wavefunction restart that stage 2 needs.

## Hubbard handling

The Hubbard parameters are written to the QE `HUBBARD` card through a `HubbardStructureData` built from the plain structure for each stage. The Yambo step runs on a plain structure, so the DFT+U correction is not applied in the SCF/NSCF there.
