# Concepts

```
structure ──► relax_1 ──► relax_2 ──► relax_3 ──► YamboWorkflow
              U initial   U final     U final     SCF → NSCF → GW/QP → BSE
              Gamma       Gamma       refined k   (on relax_3 structure)
                 └─wavefunctions─┘
```

## How the polaron is formed

The first relaxation is what makes the polaron form, so `hubbard_u_initial` should not simply repeat the physical U.

- **Stage 1 (`hubbard_u_initial`).** You choose which atoms host the extra electrons and give each of them a U that is much larger than on the other sites. Use one atom per additional electron, for example one Ti per H atom adsorbed on the slab. This much larger U localizes the electron on that atom, which is what makes the polaron form, and the ions relax around it, which creates the lattice distortion of the polaron. To make this work, those atoms must be separate kinds in the `StructureData`, so that they can get their own U in the `HubbardStructureData` (and, if needed, their own starting magnetization). See [the structure](usage.md#the-structure-the-candidate-atom-needs-its-own-kind).
- **Stage 2 (`hubbard_u_final`).** U is set back to the value you want for the final calculation, on all atoms. The calculation restarts from the wavefunctions of stage 1, so the electron starts localized and the structure relaxes with the physical U. Without this restart, the electron could delocalize again.
- **Stage 3 (`hubbard_u_final`).** The same U, with a refined k-point mesh. Its structure is the one used for GW/BSE.

If `hubbard_u_initial` is the same as `hubbard_u_final`, stage 1 has no special role, and nothing drives the electron to localize.

In the full TiO2 launch script, for example, the atom that hosts the electron has U = 10.0 eV in the initial dictionary, and every titanium kind has U = 3.5 eV in the final one.

## Spin polarization

The calculations must always be spin-polarized. A polaron is an electron localized on one site, so the system has a net spin by definition, and a non-spin-polarized calculation cannot describe it.

In the QE parameters of the relaxations, set `nspin = 2` and a nonzero `starting_magnetization` on the high-U kinds. A zero starting magnetization is not enough: QE can then converge to the non-magnetic solution and the electron delocalizes.

With two or more polarons, spin polarization also lets you choose their relative alignment through the signs of the starting magnetizations:

- **Ferromagnetic (FM):** the same sign on the high-U kinds, for example `+1` on both.
- **Antiferromagnetic (AFM):** opposite signs, for example `+1` on one and `-1` on the other, as in the full TiO2 script (`Ti2 = +1`, `Ti3 = -1`).

Each configuration is a separate run of the workflow, and the localized state of each polaron can then be analysed on its own.

If the relaxation parameters are not spin-polarized, the workflow does not stop, but it writes a `WARNING` line in the process report (`verdi process report <pk>`).

## Stages

| Stage | U values | k-points | Notes |
|---|---|---|---|
| `relax_1` | `hubbard_u_initial` | `kpoints_gamma` | Much larger U on the atoms that should host the electrons. This is where the polaron forms. |
| `relax_2` | `hubbard_u_final` | `kpoints_gamma` | Restarts from the stored wavefunctions of `relax_1`, keeping the electron localized. |
| `relax_3` | `hubbard_u_final` | `kpoints_relax3` | Refined mesh. Its structure feeds Yambo. |
| `yambo` | none (DFT only) | `kpoints_yambo` | `YamboWorkflow`: SCF, NSCF, GW, QP, then BSE on top of GW/QP. |

The final structure is returned as `final_structure`.

## Why `PwBaseWorkChain`

Each relaxation is a `PwBaseWorkChain` with `CONTROL.calculation = "relax"`. This is intentional. The public `PwRelaxWorkChain` interface excludes external `parent_folder` inputs, while `PwBaseWorkChain` supports the wavefunction restart that stage 2 needs.

## Hubbard handling

The Hubbard parameters are written to the QE `HUBBARD` card through a `HubbardStructureData` built from the plain structure for each stage. The Yambo step runs on a plain structure, so the DFT+U correction is not applied in the SCF/NSCF there.
